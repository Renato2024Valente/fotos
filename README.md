# Galeria de Imagens (Flask + Banco) — SEM SENHA

## Rodar no PC (Windows)
> Use o arquivo `requirements-local.txt` (sem Postgres) para evitar erro de instalação no Windows.

```bash
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements-local.txt
python app.py
```

Acesse:
- Galeria dos alunos: http://localhost:5000/
- Postar/Deletar: http://localhost:5000/admin

## Deploy no Render
No Render, use:
- Build command: `pip install -r requirements-render.txt`
- Start command: `gunicorn app:app`

Crie um Postgres no Render e adicione `DATABASE_URL` nas env vars do serviço.

## Importante sobre uploads no Render
Sem disco persistente, o filesystem do Render é efêmero (uploads podem sumir em redeploy/restart).
Se você tiver disco persistente, configure `UPLOAD_FOLDER` apontando para o mount.


## Se aparecer: "no such table: image"
Pare o servidor e rode:

```bash
python init_db.py
```

Depois rode novamente:

```bash
python app.py
```

(As tabelas também são criadas automaticamente na primeira requisição, por padrão.)


## Senha somente para postar/deletar
- Galerias (alunos): `/` e `/galeria/<...>`
- Gestão (postar/deletar): `/admin` (pede senha)

Senha padrão: `bicudo@26`
Para mudar:
- Local: defina `ADMIN_PASSWORD` (variável de ambiente)
- Render: Settings → Environment → `ADMIN_PASSWORD`

## Galerias fixas
- 7º Ano
- 8º Ano
- 9º Ano
- 1º Ensino Médio
- 2º Ensino Médio
