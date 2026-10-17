# Entrega contínua: imagem privada no GitHub Container Registry

## O que muda

A CI existente continua construindo os containers locais, aplicando migrations,
executando os testes Django e verificando a imagem de produção e seu HTTP/CSS.
Agora também executa os testes dos scripts de infraestrutura em `scripts/tests`.

Após push/merge em `develop` ou `main`, um segundo job aguarda a aprovação do job
de testes. Ele constrói a imagem de produção em Linux ARM64, testa suas configurações
e publica a imagem em `ghcr.io/marianapiccolo/investmind-ai:SHA_COMPLETO`.
Esse job usa um runner ARM64 padrão do GitHub, não a sua EC2.

No PR, o job de publicação é ignorado: o código ainda não foi integrado.
A EC2 pode permanecer parada durante toda a CI e a publicação.
O workflow não contém credenciais AWS, SSH ou chaves de API de produção.

A publicação gera um artifact pequeno chamado `investmind-release-SHA_COMPLETO`.
Ele contém `published-release.json`: commit, registry, plataforma, digest e URL da
execução. A imagem fica no registry; esse artifact guarda só os metadados para escolhê-la.

O deploy permanece sob seu controle: no Mac, um script valida a release e inicia
Ansible. A EC2 baixa a imagem diretamente do GHCR por digest. O Mac não precisa
construir, baixar ou enviar o arquivo grande da imagem neste novo fluxo.

Isso é entrega contínua com implantação manual, não implantação automática a cada merge.

## Arquivos

- `.github/workflows/ci.yml`: workflow completo com os jobs `test` e `publish`.
- `scripts/deploy_registry_demo.py`: seleciona a versão e inicia o novo playbook.
- `scripts/tests/test_deploy_registry_demo.py`: testes offline do seletor e seus limites.
- `infra/ansible/deploy-registry.yml`: baixa a imagem e executa o deploy conhecido.
- `docs/registry-delivery.md`: este guia.
- `docs/aws-demo-operations.md`: operação atualizada para usar o registry.
- `docs/aws-demo-deploy.md`: guia do primeiro deploy, com referência ao fluxo novo.

Os helpers de backup da fase anterior precisam estar integrados: o novo script
reutiliza suas verificações de conta/instância, SSH e escrita privada de JSON.
Não há dependência Python nova para o seletor ou seus testes.

## 1. Preparar e testar no Mac, com a EC2 parada

Após o merge do backup, com o repositório limpo:

```bash
cd ~/Documentos/GitHub/investmind-ai
source .venv/bin/activate
git switch develop
git pull --ff-only origin develop
git switch -c feature/registry-delivery
```

Copie os sete arquivos do pacote para o projeto. `ci.yml` e os dois guias de AWS
são arquivos completos que substituem suas versões anteriores. Os outros quatro são novos.

```bash
python -m unittest discover -s scripts/tests -p 'test_*.py' -v
python scripts/deploy_registry_demo.py --help
"$HOME/.venvs/investmind-ansible/bin/ansible-playbook" -i "$HOME/.config/investmind/ansible-inventory.json" infra/ansible/deploy-registry.yml --syntax-check
```

Esses comandos não ligam a EC2 nem publicam imagens. Os testes simulam AWS/SSH/Ansible;
a publicação real será validada no GitHub e o pull real, depois, na EC2.

## 2. Fazer o PR

Depois da revisão, adicione somente os sete arquivos desta entrega, faça commit,
push e PR de `feature/registry-delivery` para `develop`. Aguarde o job de testes
verde. `Publish tested ARM64 image` aparecer como skipped no PR é o esperado.
Faça o merge para validar a primeira publicação real.

## 3. Conferir a primeira publicação

No GitHub, abra Actions > InvestMind AI CI/CD > execução do push em develop.
O job `test` deve passar primeiro; depois, `Publish tested ARM64 image`.
O primeiro build ARM64 pode demorar mais por ainda não ter cache.

O GitHub autentica a publicação com o `GITHUB_TOKEN` automático da execução e
`packages: write` somente no job de publicação. Não crie um PAT para esse job.
O pacote é associado ao repositório e deve aparecer como PRIVATE em Packages.
A primeira publicação no GHCR é privada por padrão; mantenha essa visibilidade.

Ao final da execução, baixe o artifact `investmind-release-SHA_COMPLETO` na seção
Artifacts. O script do Mac aceita diretamente esse ZIP, sem precisar extraí-lo.
O artifact expira após 14 dias; os metadados selecionados ficam em cache no Mac
e a imagem permanece no GHCR até que você a exclua pelas ferramentas do GitHub.

Antes de selecionar essa release, atualize o checkout local para o commit publicado:

```bash
git switch develop
git pull --ff-only origin develop
```

O seletor exige checkout limpo e HEAD igual ao commit do artifact. Assim, os arquivos
Compose/Caddy/ambiente copiados pelo Ansible correspondem à versão da aplicação.
Se houver novos commits depois do download, escolha o artifact da versão atual ou
prepare conscientemente o checkout da versão antiga antes de fazer rollback.
O SHA de um merge/squash pode ser diferente daquele mostrado na branch de feature.

Exemplo: substitua SHA_COMPLETO pelo nome real do arquivo baixado em Downloads:

```bash
python scripts/deploy_registry_demo.py "$HOME/Downloads/investmind-release-SHA_COMPLETO.zip" --prepare-only
```

O comando valida e salva `~/.cache/investmind/registry-release.json` com permissão
600. `--prepare-only` não acessa AWS, SSH, Docker ou solicita token.
O artifact deve vir da execução do seu repositório; a verificação de formato e
labels não é uma assinatura criptográfica de origem. Não use artifacts de terceiros.

`workflow_dispatch` também foi configurado, mas o botão Run workflow só estará
disponível quando essa definição existir na branch padrão do repositório.
Para a primeira publicação use o push em develop, sem depender desse botão.

## 4. Preparar a leitura da imagem privada

Para a EC2 ler um pacote privado, gere na SUA conta GitHub um personal access token
CLASSIC com escopo `read:packages` e prazo de expiração, por exemplo 30 dias:

https://github.com/settings/tokens

Caminho: Settings > Developer settings > Personal access tokens > Tokens (classic)
> Generate new token (classic). Nome sugerido: InvestMind demo image pull.
Selecione somente `read:packages`, sem adicionar permissões de escrita ou exclusão.
Guarde o token no seu gerenciador de senhas. Não o coloque no código, nos docs,
em GitHub Secrets ou em comandos com o valor literal. O script o pedirá ocultamente.

O `GITHUB_TOKEN` do Actions publica a imagem; esse PAT de leitura autoriza o pull
privado durante o deploy. São credenciais de finalidades e ciclos de vida diferentes.

## 5. Ligar a EC2 e atualizar acesso

Use `docs/aws-demo-operations.md`: SSO, conta `990861495140`, start, inventário,
plano Terraform, validação da chave SSH e `exit` para voltar ao Mac.
Carregue a chave dedicada no agente, especialmente se ela possui passphrase:

```bash
ssh-add "$HOME/.ssh/investmind_demo"
```

Se a versão inclui migrations, faça um backup antes do deploy. A cópia atual do
banco é preservada pelo novo playbook, assim como usuários e ativos cadastrados.

## 6. Implantar a versão selecionada

Com os metadados já preparados e o checkout ainda no mesmo commit, execute no Mac:

```bash
python scripts/deploy_registry_demo.py
```

O script confirma conta, tags, VPC, estado/IP da EC2 e inventário. Testa o SSH com
validação de host ativa e então pede o PAT de leitura sem mostrá-lo na tela.
O token segue pelo ambiente do processo Ansible e pelo stdin de `docker login`.
Não aparece na linha de comando nem no JSON de release; o task tem `no_log: true`.

Na EC2, Ansible cria um diretório temporário privado de configuração Docker, faz
login, baixa `ghcr.io/...@sha256:...` e remove esse diretório em um bloco `always`,
inclusive em falhas normais. Se o computador/processo for encerrado à força, o cleanup
pode não acontecer; nesse caso, revise diretórios `/tmp/investmind-ghcr-*` na EC2.
O token temporariamente passa pelo servidor: não é um mecanismo de acesso sem credenciais.
Não compartilhe a saída de uma depuração com `no_log` desabilitado.

Após o pull, verifica plataforma ARM64 e labels de repositório/commit. O digest é
usado também em `APP_IMAGE`, de modo que uma tag alterada não muda a versão selecionada.
Compose mantém `pull_policy: never` na aplicação: a imagem já foi baixada pelo task
autenticado, e reiniciar containers não exige salvar um token permanente no servidor.

O restante repete o deploy que você já testou: configuração de ambiente/IP,
validação do proxy, PostgreSQL/Redis, pausa da aplicação, migrations, subida dos
serviços e testes HTTPS/CSS/Celery. Os segredos da aplicação continuam na EC2.
Esse deploy tem uma janela de indisponibilidade; não é uma solução de alta disponibilidade.

Teste login e compra/venda no endereço impresso. Confira também as funcionalidades
de IA/cotações que pretende mostrar. Ao terminar, pare a EC2 e confirme `stopped`.

## 7. Reutilização e custos

Para reapresentar a mesma versão, os metadados ficam preparados no Mac. Com o
checkout correspondente, basta atualizar acesso e executar novamente o seletor.
Ele pedirá o token de leitura; use um token válido ou gere outro se expirou.
Se o cache de metadados sumir, recupere seu artifact ou prepare outra versão publicada.

O GitHub documenta atualmente armazenamento/tráfego do Container Registry gratuitos.
Os jobs do Actions em repositório privado usam a franquia de minutos e podem gerar
cobrança se você exceder a franquia e permitir gastos adicionais. Artifacts/cache têm
suas próprias quotas; o artifact desta entrega contém somente um JSON pequeno.
Usamos runners padrão, cache mínimo e nenhuma EC2 para o build. Não configuramos
novos recursos pagos na AWS. Consulte o uso/budget de Actions na sua conta GitHub.
Não há exclusão automática de versões do GHCR nesta entrega.

O build antigo no Mac e `deploy-demo.yml` continuam disponíveis como alternativa;
seus metadados `release.json` são separados de `registry-release.json`. Eles podem
apontar para versões diferentes. Escolha conscientemente qual fluxo está executando.

## Referências

- https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
- https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://docs.github.com/en/billing/concepts/product-billing/github-packages
- https://github.com/docker/build-push-action
- https://github.com/actions/upload-artifact
