# Clínica Veterinária API

API REST com FastAPI, SQLAlchemy (SQLite) e Firebase Authentication.

## Instalação

Requer Python 3.10 ou superior.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux/macOS:
# source .venv/bin/activate
pip install -r requirements.txt
```

## Firebase

1. Crie um projeto em https://console.firebase.google.com/.
2. Em **Authentication > Sign-in method**, habilite um provedor de login (por exemplo E-mail/Senha).
3. Crie os usuários veterinários no Firebase Authentication (ou cadastre-os pelo aplicativo cliente).
4. Vá a **Configurações do projeto > Contas de serviço > Gerar nova chave privada**.
5. Guarde o JSON baixado como `serviceAccountKey.json` na pasta raiz. **Não inclua essa chave no GitHub.**
6. Configure a variável de ambiente com o caminho do arquivo:

```powershell
# Windows PowerShell, na raiz do projeto:
$env:FIREBASE_CREDENTIALS="./serviceAccountKey.json"
```

```bash
# Linux/macOS:
export FIREBASE_CREDENTIALS="./serviceAccountKey.json"
```

O serviço usa SQLite (`clinica.db`) por padrão. Opcionalmente, defina `DATABASE_URL`.

## Executar

```bash
uvicorn main:app --reload
```

Documentação: http://127.0.0.1:8000/docs

## Obter o Firebase ID Token

O login é realizado no **Firebase Authentication**, por um cliente (web, mobile etc.); o backend apenas valida o ID Token resultante. Exemplo de cliente web com Firebase JS SDK, após configurar o app Firebase:

```javascript
import { getAuth, signInWithEmailAndPassword } from 'firebase/auth';
const auth = getAuth();
const cred = await signInWithEmailAndPassword(auth, 'vet@exemplo.com', 'senha');
const token = await cred.user.getIdToken();
console.log(token);
```

Insira o ID Token em **Authorize** no Swagger ou use o cabeçalho `Authorization: Bearer SEU_ID_TOKEN`.

## Exemplo

```bash
curl -X POST http://127.0.0.1:8000/animais \
  -H 'Authorization: Bearer SEU_ID_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"nome":"Rex","especie":"Cachorro","raca":"Labrador","idade":4,"nome_tutor":"Ana"}'
```

Não envie `veterinario_id`: o backend preenche com o `uid` verificado pelo Firebase. Todos os métodos filtram o animal pelo `uid`; consultas a IDs de outros veterinários retornam 404.

## Testes

```bash
pytest -q
```

Os testes substituem a autenticação por uma identidade simulada usando overrides do FastAPI; não precisam da conta Firebase.

> Segurança: somente autenticar não comprova o cargo de veterinário. Em produção, configure a autorização de papel (por exemplo custom claim `role: veterinarian`), emita os privilégios apenas pelo Admin SDK e valide o papel no backend. Use HTTPS e um banco gerenciado em implantação real.
