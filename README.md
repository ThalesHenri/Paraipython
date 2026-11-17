# ☕ Expresso PB

> *"Um guia, por TH"* 🌵🐍

---

## Que peste é isso?

O **Expresso PB** é o seu jornal automatizado de João Pessoa: curto, forte e tirado na hora, com um toque de elegância vintage.

> O repositório e o pacote Python continuam se chamando `paraipython` (nome de batismo do projeto). O que mudou foi a marca do jornal.

São **duas edições por dia**: a **Edição da Manhã** (06:00), pra ler ao acordar, e a **Edição Noturna** (19:00), pra ler ao voltar pra casa. Em cada uma, um *management command* em Django varre os principais portais da capital paraibana via RSS, junta as pautas repetidas, separa tudo por tema (Cidade, Polícia, Política, Economia, Educação, Saúde, Clima & Ambiente, Esportes, Cultura), empacota numa diagramação retrô de respeito (estilo jornal de 1920) e serve um **PDF em alta qualidade** pronto pra acompanhar o cafezinho.

Tudo isso rodando nas manhas no seu servidor cPanel, porque desenvolvedor experiente não sofre em terreno desconhecido.

---

## 🧭 Como o robô trabalha

```text
06:00 e 19:00  cron ──► fetch_daily_news   (o turno sai do horário: antes do meio-dia = manhã)
                          │
                          ├─ 1. coleta    Baixa o RSS de cada fonte ativa (timeout + 3 tentativas).
                          │               Uma fonte quebrada não derruba as outras. Cada notícia
                          │               ganha um resumo que termina a frase (sem reticências)
                          │               e um tema, por palavras-chave (news/services/temas.py).
                          │
                          ├─ 2. montagem  Pega o que foi publicado DESDE A EDIÇÃO ANTERIOR
                          │               (a da manhã pega a noite e a madrugada; a noturna, o dia),
                          │               tira o que já saiu antes (inclusive a mesma história
                          │               republicada com outro link), agrupa a mesma pauta de
                          │               portais diferentes e ordena:
                          │                 • pauta que saiu em mais de um portal → manchete
                          │                 • o resto alternando os portais, até 16 notícias,
                          │                   no máximo 4 por tema
                          │
                          └─ 3. PDF       WeasyPrint renderiza o jornal (A4, cabeçalho gótico,
                                          xícara de expresso — com lua na noturna —, sumário com
                                          páginas, uma faixa por tema e Referências com o link de
                                          cada matéria) e salva em media/edicoes_pdf/.
                                          Na versão digital tudo é clicável: o título abre a
                                          matéria, o [n] pula pra referência (e volta), o
                                          sumário leva à seção, e o painel lateral do leitor
                                          de PDF lista manchete, temas e Referências.
```

**Sobre direitos autorais:** o jornal mostra só o título, um resumo curto (a linha fina do G1 ou o primeiro parágrafo do Jornal da Paraíba) e um número `[n]` que aponta pra seção de **Referências** no fim da edição, onde ficam os endereços das matérias originais (e do outro portal, quando a pauta saiu nos dois). O texto completo fica nos portais, que é onde ele mora.

---

## 🏗️ A Arquitetura do Cabra da Peste

A organização do projeto segue a máxima: *"Cada um no seu quadrado, cada um que lamba sua casseta"*.

```text
src/
├── core/                         ⚙️  settings (lê o .env), urls, wsgi
├── passenger_wsgi.py             🚪 porta de entrada do cPanel
├── news/
│   ├── models/                   📦 FonteNoticia, Noticia, Edicao (+ posição de cada notícia)
│   ├── services/                 🧠 a regra de negócio, isolada e testada
│   │   ├── coleta.py             📡 RSS → notícias limpas no banco
│   │   ├── temas.py              🏷️ palavras-chave de cada tema (ajuste aqui)
│   │   ├── montagem.py           🧩 janela, sem repeteco, relevância, seções
│   │   └── pdf_generator.py      🖨️ HTML → PDF (WeasyPrint) + miniatura da capa
│   ├── management/commands/
│   │   ├── fetch_daily_news.py   🤖 o relógio biológico do sistema (coleta + monta + PDF)
│   │   ├── generate_pdf.py       🎨 regera só o PDF (pra ajustar o layout)
│   │   └── reprocessar_noticias.py ♻️ refaz resumo e tema das notícias já salvas
│   ├── views/                    🌐 home, acervo e entrega dos PDFs
│   ├── migrations/               🗃️ inclusive as fontes iniciais (JP, g1 PB, PB Agora)
│   └── tests/                    ✅ testes, com feeds reais de exemplo
├── web/                          ℹ️  página "Sobre" + seção ☕ Apoie (pix.py gera o BR Code)
├── templates/
│   ├── news/                     🏠 index.html, acervo.html
│   └── pdf/jornal_template.html  📰 o HTML/CSS que vira arte vintage
├── static/
│   ├── css/style.css
│   ├── img/                      ☕ a xícara de expresso e a mancha de café (SVG)
│   └── fonts/                    🔤 fontes locais (OFL) usadas no site e no PDF
└── media/edicoes_pdf/            📁 onde o ouro (o PDF do dia) fica guardado
```

---

## ⚙️ Requisitos para Rodar essa Máquina

* Python 3.10+ (mais afiado que peixeira de baiano)
* Django 5.2
* WeasyPrint (precisa das bibliotecas do sistema **Pango** e **HarfBuzz**)
* feedparser, beautifulsoup4, requests, qrcode (Pix da página de apoio), pypdfium2, whitenoise, python-dotenv

Tudo no `requirements.txt`.

---

## 🚀 Como Executar Localmente (antes de subir pro cPanel)

```bash
python -m venv .venv
source .venv/bin/activate            # ou .venv\Scripts\activate no Windows
pip install -r requirements.txt

cd src
cp .env.example .env                 # em dev pode deixar DJANGO_DEBUG=True
python manage.py migrate             # cria as tabelas e já cadastra as fontes
python manage.py createsuperuser     # pra entrar no /admin

python manage.py fetch_daily_news    # coleta, monta e gera o PDF
python manage.py runserver           # http://127.0.0.1:8000
```

### Sem internet? Teste com os feeds de exemplo

```bash
python manage.py fetch_daily_news \
  --feed-local "g1 PB=news/tests/fixtures/g1_pb.xml" \
  --feed-local "Jornal da Paraíba=news/tests/fixtures/jornal_da_paraiba.xml"
```

### Outros atalhos

| Comando | O que faz |
| :--- | :--- |
| `fetch_daily_news --sem-pdf` | Coleta e monta, sem gerar PDF |
| `fetch_daily_news --sem-coleta` | Remonta a edição com o que já está no banco |
| `fetch_daily_news --turno noite` | Força o turno (`manha` ou `noite`); sem isso, vale o horário |
| `fetch_daily_news --data 2026-11-15 --turno manha` | Monta a edição de um dia e turno específicos |
| `generate_pdf` | Regera o PDF da edição mais recente |
| `generate_pdf --data 2026-11-15 --turno noite` | Regera o PDF de uma edição específica |
| `reprocessar_noticias` | Refaz resumo e tema das notícias já salvas (depois de ajustar `temas.py`) |
| `generate_pdf --html /tmp/jornal.html` | Salva também o HTML, pra depurar o layout no navegador |
| `test news` | Roda os testes |

---

## ☀️ No cPanel (Onde a mágica acontece)

1. **Suba o código** para `~/paraipython` (git clone ou upload).

2. **Setup Python App** no cPanel:
   * Python version: 3.10 ou mais nova
   * Application root: `paraipython/src`
   * Application URL: o seu domínio
   * Application startup file: `passenger_wsgi.py`
   * Application Entry point: `application`

3. **Instale as dependências** pelo terminal do cPanel (o próprio painel mostra o comando `source .../activate`):

   ```bash
   source /home/seu_usuario/virtualenv/paraipython/src/3.10/bin/activate
   cd ~/paraipython
   pip install -r requirements.txt
   ```

4. **⚠️ Teste o WeasyPrint ANTES de tudo.** Hospedagem compartilhada às vezes não tem o Pango:

   ```bash
   python -c "import weasyprint; weasyprint.HTML(string='<h1>Oxe!</h1>').write_pdf('/tmp/oxe.pdf'); print('WeasyPrint ok')"
   ```

   Se der erro de `libpango`/`libgobject`, peça ao suporte da hospedagem pra instalar o Pango. Se não rolar, o plano B é gerar o PDF em outra máquina (um VPS ou um GitHub Action) e subir só o arquivo.

5. **Configure o `.env`:**

   ```bash
   cd ~/paraipython/src
   cp .env.example .env
   python -c "import secrets; print(secrets.token_urlsafe(50))"   # cole em DJANGO_SECRET_KEY
   nano .env                                                       # DEBUG=False, domínio, banco
   ```

   **Apoio dos leitores (página Sobre → "☕ Apoie"):** sem `APOIO_PIX_CHAVE` no `.env`, a página mostra uma chave e QR codes **fictícios** com um aviso vermelho. Preencha antes de publicar:

   ```bash
   APOIO_PIX_CHAVE=sua-chave@email.com        # e-mail, CPF/CNPJ, celular (+5583...) ou chave aleatória
   APOIO_PIX_NOME=Seu Nome Completo           # como aparece no banco (até 25 caracteres)
   APOIO_PIX_CIDADE=Joao Pessoa
   APOIO_LINK_NOME=Apoia.se                   # opcional: apoio recorrente
   APOIO_LINK_URL=https://apoia.se/seu-perfil # deixe vazio pra esconder o card
   ```

   O QR do Pix é gerado sozinho a partir da chave (BR Code estático, padrão do Banco Central, sem valor fixo). Se preferir usar a imagem do QR que o seu banco gera, salve em `src/static/img/` e aponte `APOIO_PIX_QR_IMAGEM=img/meu-pix.png`. Depois de configurar, abra o app do banco e leia o QR da página pra conferir o nome do favorecido antes de divulgar.

6. **Prepare o terreno:**

   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py createsuperuser
   python manage.py fetch_daily_news      # primeira edição
   ```

   Depois clique em **Restart** na tela do Python App.

7. **Cron Jobs** — duas linhas, uma por edição (o comando é o mesmo; o turno sai do horário):

   | Minuto | Hora | Comando |
   | :--- | :--- | :--- |
   | `0` | `6` | Edição da Manhã (comando abaixo) |
   | `0` | `19` | Edição Noturna (o mesmo comando) |

   ```bash
   cd /home/seu_usuario/paraipython/src && /home/seu_usuario/virtualenv/paraipython/src/3.10/bin/python manage.py fetch_daily_news >> /home/seu_usuario/paraipython/cron.log 2>&1
   ```

   > ⏰ O cron usa o fuso do **servidor**, não o de João Pessoa. Rode `date` no terminal: se o servidor estiver em UTC, agende para **09:00** e **22:00** pra sair às 06:00 e às 19:00 daqui. O turno é calculado no fuso de João Pessoa (o `TIME_ZONE` do Django), então o comando continua o mesmo nas duas linhas.

   Mudou o horário de alguma edição? Ajuste também `PARAIPYTHON_HORARIO_MANHA` / `PARAIPYTHON_HORARIO_NOITE` no `.env` (eles aparecem no jornal e limitam a janela de notícias).

Pronto! Agora vá tomar um expresso com cuscuz enquanto o robô faz o trabalho pesado.

---

## 🗺️ Próximos passos

* [ ] Coletor por scraping para o **PB Agora** (a fonte já está cadastrada, inativa, com `tipo = scraping`)
* [ ] Notificação (e-mail/Telegram) quando uma fonte falhar no cron
* [ ] Página web de cada edição com as manchetes, além do PDF
* [ ] Ajustar as palavras-chave dos temas com o tempo (`news/services/temas.py` + `reprocessar_noticias`)

---

## 🔤 Créditos

UnifrakturMaguntia, Playfair Display, Old Standard TT e Merriweather, todas sob a SIL Open Font License (licenças em `src/static/fonts/`). A xícara e a mancha de café são desenhos próprios do projeto, em `src/static/img/`.
