"""Testa o fluxo completo pelo gateway. Requer Auth (8001), Meetings (8002), Documents (8003) e Gateway (8000) no ar."""
import sys
import uuid
import httpx

G = "http://localhost:8000"
A = M = G  # todo o tráfego passa pelo gateway
AUTH_DIRECT, MEET_DIRECT = "http://localhost:8001", "http://localhost:8002"
ok = True


def check(name, got, expected):
    global ok
    expected = expected if isinstance(expected, (list, tuple)) else [expected]
    passed = got in expected
    ok &= passed
    print(f"[{'OK' if passed else 'FALHOU'}] {name}: {got} (esperado {expected})")


tag = uuid.uuid4().hex[:6]
def reg(n): return httpx.post(f"{A}/auth/register", json={"name": n, "email": f"{n.lower()}{tag}@escritorio.com", "password": "senha-forte-1"})
def login(n, pw="senha-forte-1"): return httpx.post(f"{A}/auth/login", json={"email": f"{n.lower()}{tag}@escritorio.com", "password": pw})
def H(tok): return {"Authorization": f"Bearer {tok}"}

# --- autenticação
r1, r2, r3 = reg("Maria"), reg("Joao"), reg("Carla")
check("1. Cadastrar 3 usuários", (r1.status_code, r2.status_code, r3.status_code), [(201, 201, 201)])
check("1b. Resposta não expõe hash", "password_hash" in r1.json(), False)
check("1c. E-mail duplicado", reg("Maria").status_code, 409)
check("1d. Senha curta", httpx.post(f"{A}/auth/register", json={"name": "X", "email": f"x{tag}@a.com", "password": "123"}).status_code, 400)
check("1e. Login com senha errada", login("Maria", "errada-errada").status_code, 401)
tm, tj, tc = (login(n).json()["access_token"] for n in ("Maria", "Joao", "Carla"))
check("1f. /auth/me com token", httpx.get(f"{A}/auth/me", headers=H(tm)).json()["name"], "Maria")
check("1g. /auth/me sem token", httpx.get(f"{A}/auth/me").status_code, 401)
check("1h. Token adulterado", httpx.get(f"{A}/auth/me", headers=H(tm + "x")).status_code, 401)
idm, idj, idc = (httpx.get(f"{A}/auth/me", headers=H(t)).json()["id"] for t in (tm, tj, tc))

# --- reuniões
base = {"title": "Audiência preliminar", "room": "Sala 2", "start_time": "2030-11-10T14:00", "end_time": "2030-11-10T15:00"}
check("2a. Criar sem token", httpx.post(f"{M}/meetings", json={**base, "participant_ids": [idj]}).status_code, 401)
r = httpx.post(f"{M}/meetings", json={**base, "participant_ids": [idj]}, headers=H(tm))
check("2. Criar reunião autenticada", r.status_code, 201)
mid = r.json()["id"]
check("2b. Organizador incluído automaticamente", sorted(r.json()["participant_ids"]), [sorted([idm, idj])])
check("3. Participante inexistente", httpx.post(f"{M}/meetings", json={**base, "participant_ids": [999999]}, headers=H(tm)).status_code, 404)
r = httpx.post(f"{M}/meetings", json={**base, "start_time": "2030-11-10T14:30", "end_time": "2030-11-10T15:30", "participant_ids": [idj]}, headers=H(tm))
check("4. Sobreposição", r.status_code, 409); print("    ->", r.json()["detail"])
check("4b. Sobreposição como organizador diferente", httpx.post(f"{M}/meetings", json={**base, "participant_ids": [idm]}, headers=H(tj)).status_code, 409)
check("5. end antes de start", httpx.post(f"{M}/meetings", json={**base, "start_time": "2030-11-10T16:00", "end_time": "2030-11-10T15:00"}, headers=H(tm)).status_code, 400)
check("5b. Reunião adjacente", httpx.post(f"{M}/meetings", json={**base, "start_time": "2030-11-10T15:00", "end_time": "2030-11-10T16:00"}, headers=H(tm)).status_code, 201)

# --- permissões
check("6. Participante lê detalhe", httpx.get(f"{M}/meetings/{mid}", headers=H(tj)).status_code, 200)
check("6b. Não participante não lê", httpx.get(f"{M}/meetings/{mid}", headers=H(tc)).status_code, 403)
check("6c. Não participante não lista", [m["id"] for m in httpx.get(f"{M}/meetings", headers=H(tc)).json()], [[]])
check("6d. Participante não edita", httpx.put(f"{M}/meetings/{mid}", json={"title": "Y"}, headers=H(tj)).status_code, 403)
check("6e. Participante não cancela", httpx.delete(f"{M}/meetings/{mid}", headers=H(tj)).status_code, 403)
check("6f. Organizador edita", httpx.put(f"{M}/meetings/{mid}", json={"title": "Novo título"}, headers=H(tm)).json()["title"], "Novo título")
r = httpx.delete(f"{M}/meetings/{mid}", headers=H(tm))
check("7a. Organizador cancela", (r.status_code, r.json()["status"]), [(200, "cancelled")])
check("7b. Editar cancelada", httpx.put(f"{M}/meetings/{mid}", json={"title": "Z"}, headers=H(tm)).status_code, 409)
check("7c. Horário liberado", httpx.post(f"{M}/meetings", json={**base, "participant_ids": [idj]}, headers=H(tm)).status_code, 201)

# --- perfil
check("8. Trocar senha", httpx.post(f"{A}/auth/change-password", json={"current_password": "senha-forte-1", "new_password": "outra-senha-2"}, headers=H(tc)).status_code, 204)
check("8b. Login com nova senha", login("Carla", "outra-senha-2").status_code, 200)
check("8c. Excluir conta", httpx.delete(f"{A}/auth/me", headers=H(tc)).status_code, 204)
check("8d. Token de conta excluída", httpx.get(f"{A}/auth/me", headers=H(tc)).status_code, 401)

# --- documentos
reg("Ana"); ta = login("Ana").json()["access_token"]
dm = httpx.post(f"{M}/meetings", json={**base, "title": "Reunião de processo", "start_time": "2032-05-01T09:00",
                "end_time": "2032-05-01T10:00", "participant_ids": [idj]}, headers=H(tm)).json()["id"]


def up(tok, meeting, name="ata.txt", content=b"ATA v1", typ="ata", title="Ata da reunião"):
    return httpx.post(f"{G}/documents", headers=H(tok), files={"file": (name, content, "text/plain")},
                      data={"meeting_id": str(meeting), "doc_type": typ, "title": title, "description": "d"})


r = up(tj, dm); check("14. Participante envia documento", r.status_code, 201)
did = r.json()["id"]
check("14b. Metadados", (r.json()["doc_type"], r.json()["current_version"], r.json()["filename"], r.json()["size"]), [("ata", 1, "ata.txt", 6)])
check("14c. Resposta não expõe armazenamento interno", "stored_name" in str(r.json()), False)
check("14d. Não participante não envia", up(ta, dm).status_code, 403)
check("14e. Extensão proibida", up(tj, dm, "virus.exe").status_code, 400)
check("14f. Tipo inválido", up(tj, dm, typ="x").status_code, 400)
check("14g. Arquivo grande demais", up(tj, dm, content=b"x" * (11 * 1024 * 1024)).status_code, 413)
check("14h. Reunião cancelada", up(tm, mid).status_code, 409)
check("14i. Reunião inexistente", up(tm, 99999).status_code, 404)
r = httpx.get(f"{G}/documents/{did}/download", headers=H(tm)); check("15. Download", (r.status_code, r.content), [(200, b"ATA v1")])
check("15b. Não participante não baixa", httpx.get(f"{G}/documents/{did}/download", headers=H(ta)).status_code, 403)
check("15c. Não participante não vê detalhe", httpx.get(f"{G}/documents/{did}", headers=H(ta)).status_code, 403)
r = httpx.post(f"{G}/documents/{did}/versions", files={"file": ("ata.txt", b"ATA v2 revisada", "text/plain")}, headers=H(tm))
check("16. Nova versão", (r.status_code, r.json()["current_version"], len(r.json()["versions"])), [(201, 2, 2)])
check("16b. Download da versão atual", httpx.get(f"{G}/documents/{did}/download", headers=H(tj)).content, b"ATA v2 revisada")
check("16c. Download da versão 1", httpx.get(f"{G}/documents/{did}/download?version=1", headers=H(tj)).content, b"ATA v1")
check("16d. Versão inexistente", httpx.get(f"{G}/documents/{did}/download?version=9", headers=H(tj)).status_code, 404)
check("17. Listar por reunião", [d["id"] for d in httpx.get(f"{G}/documents", params={"meeting_id": dm}, headers=H(tj)).json()], [[did]])
check("17b. Listar de todas as minhas reuniões", did in [d["id"] for d in httpx.get(f"{G}/documents", headers=H(tj)).json()], True)
check("17c. Não participante lista vazio", httpx.get(f"{G}/documents", headers=H(ta)).json(), [[]])
check("17d. Filtro por tipo", httpx.get(f"{G}/documents", params={"doc_type": "processo"}, headers=H(tj)).json(), [[]])
check("18. Autor edita metadados", httpx.put(f"{G}/documents/{did}", json={"title": "Ata final", "doc_type": "processo"}, headers=H(tj)).json()["title"], "Ata final")
pid = up(tm, dm, "proc.pdf", b"%PDF-1.4", "processo", "Processo 123").json()["id"]
check("18b. Outro participante não edita", httpx.put(f"{G}/documents/{pid}", json={"title": "x"}, headers=H(tj)).status_code, 403)
check("18c. Outro participante não exclui", httpx.delete(f"{G}/documents/{pid}", headers=H(tj)).status_code, 403)
check("19. Organizador exclui documento de outro", httpx.delete(f"{G}/documents/{did}", headers=H(tm)).status_code, 204)
check("19b. Documento excluído", httpx.get(f"{G}/documents/{did}", headers=H(tm)).status_code, 404)
check("19c. Acesso direto ao Documents sem chave", httpx.get("http://localhost:8003/documents").status_code, 403)

# --- gateway
r = httpx.get(f"{G}/health"); check("10. /health agregado", (r.status_code, r.json()["status"]), [(200, "ok")])
check("10b. Rota desconhecida", httpx.get(f"{G}/xyz").status_code, 404)
check("10c. Protegida sem token (barrada no gateway)", httpx.get(f"{G}/meetings").status_code, 401)
check("10d. X-Request-ID na resposta", "x-request-id" in httpx.get(f"{G}/meetings", headers=H(tm)).headers, True)
check("11. Acesso direto ao Auth sem chave", httpx.get(f"{AUTH_DIRECT}/users").status_code, 403)
check("11b. Acesso direto ao Meetings sem chave", httpx.get(f"{MEET_DIRECT}/meetings", headers={"X-User-Id": "1"}).status_code, 403)
r = httpx.post(f"{G}/meetings", json={**base, "start_time": "2031-03-01T10:00", "end_time": "2031-03-01T11:00"},
               headers={**H(tm), "X-User-Id": str(idj)})
check("12. Cabeçalho X-User-Id forjado é ignorado", r.json().get("organizer_id"), idm)
codes = [login("Maria", "errada-errada").status_code for _ in range(15)]
check("13. Rate limit no login (429)", 429 in codes, True)

if "--skip-503" not in sys.argv:
    input("\nDerrube o Auth Service (Ctrl+C no terminal 1) e pressione ENTER... ")
    check("9. Auth fora do ar (503 pelo gateway)", httpx.post(f"{M}/meetings", json={**base, "participant_ids": [idj]}, headers=H(tm)).status_code, 503)

print("\nTUDO OK" if ok else "\nHÁ FALHAS")
sys.exit(0 if ok else 1)
