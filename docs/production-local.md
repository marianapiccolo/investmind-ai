# InvestMind AI: preparação para produção

Esta etapa acrescenta Gunicorn, WhiteNoise e configurações específicas de
produção. O teste local usa HTTP apenas na interface de loopback do Mac.
A configuração efetiva de HTTPS e o deploy na AWS virão nas próximas fases.

## Fases até a primeira versão hospedada

| Fase | Resultado |
| --- | --- |
| Docker local — concluída | Django, PostgreSQL/pgvector, Redis, Worker e Beat reproduzíveis com Compose. |
| CI — concluída | GitHub Actions construindo a imagem e executando os testes nos PRs. |
| Preparação de produção — atual | Gunicorn, DEBUG=false, estáticos coletados e verificações de produção no CI. |
| AWS e Terraform | Escolha dos recursos e custos, acesso à conta, infraestrutura definida por código e plano revisável. |
| Configuração com Ansible | Servidor Linux preparado para executar os containers, com configuração reproduzível. |
| Primeiro deploy | Aplicação, Worker e Beat funcionando na AWS, banco persistente, HTTPS e fluxos reais verificados. |
| CD e recuperação | Imagens versionadas, implantação automatizada e procedimento para voltar à versão anterior. |
| Operação e revisão | Logs, backups com restauração verificada, limites de custo, segurança e pendências OpenAPI/fuso horário revisadas. |
| Fechamento da V1 | README, arquitetura, documentação da API e roteiro de demonstração reproduzível. |

A V1 estará concluída quando a aplicação hospedada funcionar por HTTPS,
as funcionalidades existentes de carteiras e IA forem verificadas nesse
ambiente, as entregas puderem ser repetidas e houver recuperação e documentação.
Novas funcionalidades serão uma evolução posterior dessa versão.

## Arquivos desta etapa

| Arquivo | Função |
| --- | --- |
| requirements-production.txt | Reutiliza requirements.txt e acrescenta Gunicorn 26.2.0 e WhiteNoise 6.12.0. |
| config/settings_production.py | Importa as configurações existentes e define DEBUG=false, estáticos e segurança de produção. |
| Dockerfile.production | Constrói a imagem de produção e executa collectstatic durante a construção. |
| compose.production-test.yaml | Executa Gunicorn na porta 8001 e conecta ao banco Docker existente. |
| scripts/create_production_test_env.py | Gera um arquivo privado de teste com nova chave Django e valores fictícios para APIs. |
| .github/workflows/ci.yml | Substituição completa do workflow, adicionando construção e smoke tests da imagem de produção. |
| docs/production-local.md | Este guia. |

O Dockerfile e o Compose de desenvolvimento permanecem disponíveis.
O settings.py original e o requirements.txt continuam sendo as bases do projeto.

## Conceitos

Gunicorn é o processo que executa a aplicação Django por WSGI.
WhiteNoise atende os arquivos estáticos coletados, como o CSS do admin.
collectstatic reúne e processa os arquivos em staticfiles dentro da imagem.
O storage utilizado também gera nomes com hash e versões comprimidas.

settings_production.py importa as configurações existentes e sobrescreve as
que precisam mudar. WhiteNoise é inserido após SecurityMiddleware em uma cópia
da lista; o middleware de desenvolvimento não é modificado.

A imagem de produção contém o código e os estáticos. Não monta a pasta do
projeto do Mac em /app. Alterações no código exigem reconstruir essa imagem.
Os segredos .env não são copiados para ela, conforme o .dockerignore existente.

O Dockerfile fornece apenas valores fictícios à execução de collectstatic.
Os valores reais de execução são injetados quando o container inicia.

## Instalação dos arquivos completos

Baixe InvestMind_Production.zip para Downloads. Na raiz do repositório,
na branch feature/production-config, execute:

```bash
unzip -n "$HOME/Downloads/InvestMind_Production.zip" -d "$HOME/Downloads"

mkdir -p config scripts docs .github/workflows

cp "$HOME/Downloads/InvestMind_Production/requirements-production.txt" .
cp "$HOME/Downloads/InvestMind_Production/Dockerfile.production" .
cp "$HOME/Downloads/InvestMind_Production/compose.production-test.yaml" .
cp "$HOME/Downloads/InvestMind_Production/config/settings_production.py" config/
cp "$HOME/Downloads/InvestMind_Production/scripts/create_production_test_env.py" scripts/
cp "$HOME/Downloads/InvestMind_Production/.github/workflows/ci.yml" .github/workflows/
cp "$HOME/Downloads/InvestMind_Production/docs/production-local.md" docs/
```

Se o download tiver outro nome ou destino, ajuste o primeiro comando.
O ci.yml é o arquivo completo atualizado, e substitui a versão desta conversa.

## Teste local, um comando por vez

Mantenha o Docker Desktop aberto e use a raiz do projeto como diretório atual.
Confirme o banco e o Redis do desenvolvimento:

```bash
docker compose up -d --wait db redis
```

Crie o ambiente privado de teste:

```bash
python scripts/create_production_test_env.py
```

O script mantém o .env original, cria .env.production-test com permissões 600
e não imprime os valores. Se o arquivo de teste já existe, ele o preserva.
As credenciais do banco são as mesmas do ambiente Docker existente.
Uma chave Django nova e longa é gerada para satisfazer as verificações de
produção. As chaves efetivas de OpenAI e Alpha Vantage são substituídas por
valores fictícios para este teste.

As regras atuais de .gitignore e .dockerignore excluem .env.production-test.

Confira o Compose e construa a imagem:

```bash
docker compose --project-name investmind-ai-production-test -f compose.production-test.yaml config --quiet
docker compose --project-name investmind-ai-production-test -f compose.production-test.yaml build web
```

Durante a construção, procure a conclusão de collectstatic. Se ele indicar
arquivo estático ausente ou qualquer outro erro, pare e envie o erro antes
de continuar. Não envie o conteúdo de arquivos .env.

Inicie o Gunicorn e confira o estado e os logs:

```bash
docker compose --project-name investmind-ai-production-test -f compose.production-test.yaml up -d --wait --wait-timeout 120 web
docker compose --project-name investmind-ai-production-test -f compose.production-test.yaml ps
docker compose --project-name investmind-ai-production-test -f compose.production-test.yaml logs --tail=50 web
```

O serviço web deve ficar healthy. Nos logs, procure a inicialização do Gunicorn
e seus workers. Esses workers HTTP são diferentes do Celery Worker.

Confira que a configuração utilizada é a de produção e DEBUG está desativado:

```bash
docker compose --project-name investmind-ai-production-test -f compose.production-test.yaml exec web python manage.py shell -c 'from django.conf import settings; print(settings.SETTINGS_MODULE); print("DEBUG:", settings.DEBUG)'
```

O resultado deve incluir config.settings_production e DEBUG: False.

Verifique a página do admin e seu CSS:

```bash
curl --fail --silent --show-error --output /dev/null http://127.0.0.1:8001/admin/login/
curl --fail --silent --show-error --output /dev/null http://127.0.0.1:8001/static/admin/css/base.css
```

Esses comandos podem terminar sem saída; curl retorna erro se a resposta falhar.
Abra http://127.0.0.1:8001/admin/ e confira que os estilos carregam e você
consegue entrar com o usuário existente. O banco é compartilhado com o
desenvolvimento, então não precisa criar outro superusuário.

A nova chave de sessão pode exigir novo login ao alternar entre as portas
8000 e 8001. Use dados de demonstração neste banco local.

## Limites do teste local

Esta etapa verifica Gunicorn, configurações e estáticos. Não inicia um novo
Celery Worker nem outro Beat. O cache usa o banco lógico 3 do Redis e a fila
usa o banco lógico 4, separados dos bancos lógicos 1 e 2 do desenvolvimento.
As tarefas desse ambiente de verificação não devem ser consumidas pelo Worker
de desenvolvimento. Os fluxos reais de IA e tarefas serão verificados com os
serviços e as credenciais do ambiente hospedado.

O modo DJANGO_LOCAL_PRODUCTION_TEST=true libera HTTP e cookies locais somente
para hosts de loopback. O Compose deste teste publica a porta em 127.0.0.1.
Na configuração padrão de produção, esse modo fica false, HTTPS é obrigatório
e os cookies são Secure. O arquivo de teste não é a configuração do deploy AWS.

SECURE_HSTS_INCLUDE_SUBDOMAINS e SECURE_HSTS_PRELOAD permanecem false até
definirmos o domínio e sua política de HTTPS. check --deploy pode emitir os
avisos correspondentes. A confiança em X-Forwarded-Proto só será habilitada
quando configurarmos um proxy confiável que controle esse cabeçalho.

Não é necessário repetir manualmente a suíte sem novas alterações no backend:
o PR executará os testes existentes e as novas verificações de produção no CI.

## Git e primeira execução do CI ampliado

Depois que as verificações locais passarem:

```bash
git status --short --branch
git add requirements-production.txt Dockerfile.production compose.production-test.yaml config/settings_production.py scripts/create_production_test_env.py .github/workflows/ci.yml docs/production-local.md
git diff --cached --check
git diff --cached --stat
git commit -m "Prepare Django production runtime"
git push -u origin feature/production-config
```

O arquivo .env.production-test não deve aparecer no status ou no commit.
Abra um PR de feature/production-config para develop. O workflow agora verifica
a imagem de desenvolvimento, as migrações e os testes, e também constrói a
imagem de produção, inicia Gunicorn e consulta o admin e o CSS por HTTP local.

No CI, DEVELOPMENT_NETWORK aponta para a rede temporária investmind-ci_default.
O banco de teste do Django é separado. A verificação do Gunicorn usa o banco
temporário da aplicação do CI, que recebeu as migrações antes.

Os dados do CI são descartados. A limpeza remove primeiro o web de produção
e depois o PostgreSQL/Redis temporários. Os volumes do Mac não participam.

Antes de integrar o PR, confira o resultado das novas etapas. Se uma falhar,
envie o nome da etapa e o erro relevante para corrigirmos.

## Parar o teste local

```bash
docker compose --project-name investmind-ai-production-test -f compose.production-test.yaml down
```

O banco e o Redis compartilhados continuam disponíveis no ambiente local.

## Validação e referências

Os arquivos foram conferidos quanto à sintaxe Python, YAML e shell, geração
segura do arquivo de teste, isolamento de fila/cache, configuração de rede
e consistência do CI. O repositório completo e o Docker Engine do Mac não
estão neste ambiente; o build e as respostas HTTP precisam ser confirmados
pelos comandos acima e pela primeira execução do PR.

- https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/
- https://whitenoise.readthedocs.io/en/stable/django.html
- https://gunicorn.org/reference/settings/
- https://pypi.org/project/gunicorn/
- https://pypi.org/project/whitenoise/
- https://docs.docker.com/compose/how-tos/networking/
