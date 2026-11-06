# 🗞️ Paraípython

> *"Um guia, por TH"* 🌵🐍

---

## Que peste é isso? 

O **Paraípython** é o seu agregador de notícias automatizado de João Pessoa com um toque de elegância vintage. 

Enquanto você dorme o sono dos justos, um *management command* em Django acorda às 06:00 em ponto, varre os principais portais da capital paraibana via RSS, limpa a bagunça com BeautifulSoup, empacota tudo em uma diagramação retrô de respeito (estilo jornal de 1920) e cospe um **PDF em alta qualidade** pronto para download. 

Tudo isso rodando nas manhas no seu servidor cPanel, porque desenvolvedor experiente não sofre em terreno desconhecido.

---

## 🏗️ A Arquitetura do Cabra da Peste

A organização do projeto segue a máxima: *"Cada um no seu quadrado, cada um que lamba sua casseta"*.

```text
paraipython/
├── apps/news/
│   ├── models/             📦 Fontes, Notícias e Edições separadas por domain-driven gambiarra
│   ├── views/              📦 Separação fina entre o front público e o gerador de PDF
│   └── management/commands/ 🤖 O relógio biológico do sistema (fetch + generate)
├── templates/pdf/          🎨 O HTML/CSS que o WeasyPrint transforma em arte vintage
└── media/edicoes_pdf/      📁 Onde o ouro (o PDF do dia) fica guardado

⚙️ Requisitos para Rodar essa Máquina

Antes de botar o bloco na rua, certifique-se de que o seu ambiente tem o veneno necessário:

    Python 3.x (Mais afiado que peixeira de baiano)

    Django (Quem poderia imaginar)

    WeasyPrint (Para fazer o CSS virar um PDF de respeito sem resenha)

    Bibliotecas auxiliares: feedparser, beautifulsoup4, requests

🚀 Como Executar Localmente (Antes de subir pro cPanel)

    Clone o repositório e ative o seu ambiente virtual favorito:
    Bash

    python -m venv venv
    source venv/bin/activate  # ou venv\Scripts\activate se estiver no Windows

    Arrocha nas dependências:
    Bash

    pip install -r requirements.txt

    Rode as migrações (pra criar as tabelas no banco de dados):
    Bash

    python manage.py migrate

    Acione o bot de coleta manualmente para testar se a internet está pegando:
    Bash

    python manage.py fetch_daily_news

☀️ No cPanel (Onde a mágica acontece)

    Configure o seu aplicativo Python no cPanel apontando para o Django.

    Vá na aba de Cron Jobs e adicione a tarefa para rodar todo santo dia às 06:00 AM:
    Bash

    /home/seu_usuario/virtualenv/sua_pasta/3.10/bin/python /home/seu_usuario/paraipython/manage.py fetch_daily_news

    Pronto! Agora vá tomar um café com cuscuz enquanto o robô faz o trabalho pesado.