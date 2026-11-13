# Meu Controle

Aplicativo pessoal para registrar receitas e despesas, consultar o saldo por mês e exportar os lançamentos em CSV. A interface funciona no navegador do computador e do celular.

## Executar no Windows

Requer Python 3.10 ou mais recente.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:APP_MODE = "local"
streamlit run app.py
```

O modo local não exige login e grava em `.data/finance.db`, apenas neste computador. Use `APP_MODE=local` somente durante o desenvolvimento; o modo padrão é produção e exige login e Google Sheets.

## Usar no celular

Para registrar e consultar os mesmos dados em qualquer lugar, publique o app no Streamlit Community Cloud. O app usa a data local do navegador como sugestão, então o celular fornece a data do próprio dispositivo.

## Configuração remota

1. No Google Cloud, ative a Google Sheets API, crie uma conta de serviço e uma credencial OAuth do tipo **Web application**.
2. Crie uma planilha no Google Drive e compartilhe-a com o e-mail da conta de serviço, permitindo edição.
3. Configure a URI de redirecionamento do cliente OAuth como `https://SEU-APP.streamlit.app/oauth2callback` (e a URI equivalente do app local, se for testar o login local).
4. Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` para desenvolvimento, ou cole os valores na área **Secrets** do Streamlit Community Cloud. Preencha `allowed_email` com sua conta Google e substitua todos os valores de exemplo.
5. No Cloud, use a URL real do app em `redirect_uri`. O app só libera acesso ao e-mail autorizado e verificado; sem login ou sem configuração do Sheets, não abre os dados nem usa SQLite.

O arquivo `.streamlit/secrets.toml` e o banco local estão ignorados pelo Git. Nunca envie credenciais reais ao GitHub. O app cria a aba `Lancamentos` e seus cabeçalhos automaticamente. Gere um `cookie_secret` aleatório e forte; não reutilize a chave privada da conta de serviço para esse campo.

## Campos

Cada lançamento registra data, tipo, categoria, descrição, valor e horário de criação. O resumo mostra ganhos, gastos, saldo e despesas por categoria para o mês escolhido.