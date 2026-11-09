# Sistema de Gerenciamento de Reuniões (Microsserviços + API Gateway)

Python + FastAPI + SQLite + REST.

```
Navegador / cliente ──► API Gateway (8000) ──┬──► Auth Service (8001)       auth.db
                                             ├──► Meetings Service (8002)   meetings.db
                                             └──► Documents Service (8003)  documents.db + storage/
```
**Todo o tráfego entra pelo gateway.** Os serviços recusam (403) qualquer chamada sem a chave interna
(`X-Internal-Key`), então não podem ser acessados diretamente.

| Componente | Porta | Responsabilidade |
|---|---|---|
| API Gateway | 8000 | Roteamento, autenticação, identidade, rate limit, CORS, health, erros padronizados |
| Auth Service | 8001 | Cadastro, login (JWT), perfil e diretório de usuários |
| Meetings Service | 8002 | Ciclo de vida das reuniões |
| Documents Service | 8003 | Atas, processos e outros documentos das reuniões (com versões) |

## Rodar (5 terminais)
```bash
cd auth_service     && pip install -r requirements.txt && uvicorn main:app --port 8001 
cd meetings_service && pip install -r requirements.txt && uvicorn main:app --port 8002
cd documents_service && pip install -r requirements.txt && uvicorn main:app --port 8003
cd gateway          && pip install -r requirements.txt && uvicorn main:app --port 8000
cd frontend         && python -m http.server 5500          # http://localhost:5500
```
Se vier da versão anterior, apague os `.db` antigos. Variáveis de ambiente úteis:
`INTERNAL_KEY` (a mesma em todos os processos), `AUTH_SECRET` (Auth), `AUTH_URL`/`MEETINGS_URL`/`DOCUMENTS_URL` (gateway), `MAX_BODY_MB` (gateway, 12), `MAX_UPLOAD_MB` e `DOCS_STORAGE` (Documents),
`ALLOWED_ORIGINS`, `REQUEST_TIMEOUT`, `RATE_LOGIN`, `RATE_REGISTER`. **Troque `INTERNAL_KEY` e `AUTH_SECRET` em produção.**

## O que o gateway faz
- **Roteamento** por prefixo (`GET /routes` lista a tabela): `/auth/*` e `/users/*` → Auth; `/meetings/*` → Meetings; `/documents/*` → Documents.
- **Autenticação centralizada:** rotas protegidas exigem `Bearer` válido; o gateway valida no Auth Service e responde 401 sem sequer chamar o serviço de destino. Públicas: `POST /auth/register` e `POST /auth/login`.
- **Identidade confiável:** injeta `X-User-Id` (o Meetings usa esse valor) e descarta `X-User-Id`/`X-Internal-Key`/`X-Request-ID` enviados pelo cliente, impedindo falsificação.
- **Rate limit por IP** (janela de 60 s): login 10, cadastro 10 → 429 com `Retry-After`.
- **Erros padronizados:** 404 rota inexistente, 503 serviço fora do ar, 504 timeout, sempre `{"detail": ...}`.
- **Rastreabilidade:** `X-Request-ID` em toda resposta e log de cada requisição (método, rota, status, tempo).
- **`GET /health`:** estado do gateway e dos serviços (200 ou 503 "degraded"). **CORS** só no gateway.

## Auth Service (via gateway)
| Método | Rota | Descrição | Sucesso | Erros |
|---|---|---|---|---|
| POST | /auth/register | Cria conta (senha ≥ 8) | 201 | 400, 409 |
| POST | /auth/login | Devolve `access_token` (JWT) | 200 | 401, 429 |
| GET / PUT / DELETE | /auth/me | Ver, atualizar, excluir a própria conta | 200 / 200 / 204 | 401, 409 |
| POST | /auth/change-password | Troca a senha | 204 | 400 |
| GET | /users, /users/{id} | Diretório | 200 | 401, 404 |

Senhas com PBKDF2-SHA256 + salt; JWT HS256 com expiração de 1 h.

## Meetings Service (via gateway; exige `Authorization: Bearer <token>`)
- O usuário autenticado é o **organizador** e entra como participante. Só o organizador edita/cancela (403 para os demais).
- `GET /meetings` lista apenas as reuniões em que o usuário participa; `GET /meetings/{id}`: 403 se não participa.
- Regras: fim > início (400), participantes existentes (404), sem conflito de horário (409), reunião cancelada não edita (409).

## Documents Service (via gateway; exige `Authorization: Bearer <token>`)
Documentos pertencem a uma reunião; **o acesso segue a participação na reunião** (o serviço pergunta ao Meetings Service).
| Método | Rota | Descrição | Sucesso | Erros |
|---|---|---|---|---|
| POST | /documents | Envia documento (`multipart`: `meeting_id`, `doc_type`, `title`, `description`, `file`) | 201 | 400, 403, 404, 409, 413 |
| GET | /documents | Lista (`?meeting_id=`, `?doc_type=`); sem `meeting_id` traz as de todas as minhas reuniões | 200 | 403, 404 |
| GET | /documents/{id} | Detalhe com histórico de versões | 200 | 403, 404 |
| PUT | /documents/{id} | Edita título/tipo/descrição | 200 | 400, 403, 404 |
| POST | /documents/{id}/versions | Envia nova versão (`file`) | 201 | 400, 403, 409, 413 |
| GET | /documents/{id}/download | Baixa o arquivo (`?version=N` para versões antigas) | 200 | 403, 404 |
| DELETE | /documents/{id} | Exclui documento e todas as versões | 204 | 403, 404 |

- Tipos: `ata`, `processo`, `outro`. Extensões aceitas: pdf, doc, docx, odt, rtf, txt, md, xls, xlsx, csv, ppt, pptx, png, jpg, jpeg. Limite: 10 MB por arquivo.
- Qualquer participante vê, baixa, envia documentos e novas versões. Editar/excluir: autor do documento ou organizador da reunião.
- Reunião cancelada não aceita novos documentos/versões (consulta e download continuam).
- Arquivos ficam em `documents_service/storage/` com nome aleatório (o nome enviado é só metadado) e SHA-256 registrado por versão.

## Testar
Com os quatro processos no ar: `pip install httpx && python test_flow.py` (`--skip-503` pula o teste de serviço fora do ar).
Aguarde 1 min antes de repetir, por causa do rate limit.

## Limitações conhecidas
- Rate limit e chave interna são simples (em memória / chave estática); em produção, use Redis e mTLS ou rede privada.
- O gateway consulta o Auth a cada requisição protegida (sem cache, para respeitar exclusão de conta imediatamente).
- Sem refresh token nem revogação antes da expiração; `recurrence` só é armazenada; excluir conta não remove suas reuniões.
