# Backup e teste de restauração do InvestMind AI

Todos os comandos deste guia são executados no Mac, dentro do projeto.
O script acessa a EC2 por SSH somente no comando `backup`.
O comando `verify` trabalha exclusivamente no Docker local, sem consultar a AWS.

## O que estamos protegendo

O código está no Git. Os registros de usuários, ativos, carteiras, posições,
transações, relatórios e conhecimento estão no PostgreSQL da EC2.
Um volume mantém esses dados entre reinicializações; um backup permite recuperá-los
em outro banco. Nesta etapa vamos exportar o banco e testar a recuperação local.

Usamos `pg_dump --format=custom`, que exporta uma visão consistente do banco e
comprime o arquivo. `pg_restore` recupera estrutura e dados desse formato.
Não execute um deploy/migrations ao mesmo tempo que o backup.

## Arquivos desta entrega

- `scripts/demo_database_backup.py`: exportação e teste de restauração.
- `scripts/tests/test_demo_database_backup.py`: testes offline da lógica do script.
- `docs/aws-demo-backup.md`: este guia.
- `docs/aws-demo-operations.md`: rotina de apresentação e de atualização do site.

O script usa somente a biblioteca padrão do Python, além dos programas já usados
no projeto: AWS CLI, Terraform, SSH e Docker. Nenhum pacote Python novo é necessário.

## 1. Preparar o código no Mac

Depois do merge do PR de deploy e com `git status --short` limpo:

```bash
cd ~/Documentos/GitHub/investmind-ai
source .venv/bin/activate
git switch develop
git pull --ff-only origin develop
git switch -c feature/database-backup
```

Copie os quatro arquivos do ZIP para suas pastas correspondentes no projeto.
Eles são arquivos novos; não substituem Dockerfiles, Compose ou dados existentes.

```bash
python -m unittest discover -s scripts/tests -p test_demo_database_backup.py -v
python scripts/demo_database_backup.py --help
```

Esses testes usam simulações de AWS, SSH e Docker. Eles NÃO fazem uma exportação
ou restauração real. Essa validação acontece nos passos 3 e 4.

## 2. Preparar o acesso à EC2

Siga `docs/aws-demo-operations.md` até confirmar a conexão SSH.
Para fazer somente o backup, não é necessário reconstruir a imagem da aplicação
nem executar um deploy para configurar o HTTPS do IP novo. O backup usa SSH.
O PostgreSQL precisa estar funcionando na EC2.

## 3. Exportar e guardar no Mac

```bash
python scripts/demo_database_backup.py backup
```

O script verifica a conta `990861495140`, a região `us-east-1`, os outputs do
Terraform e os dados da instância na AWS. Exige as tags e a chave do InvestMind,
instância ligada e chave SSH do host já confiada. Não aceita hosts novos sozinho.
Usa PostgreSQL 18 e a release apontada por `/opt/investmind/current`.

O dump sai diretamente do container PostgreSQL pela conexão SSH e é escrito no Mac.
Não é criado um arquivo grande no disco da EC2 e a senha PostgreSQL permanece no
ambiente do container. O script não imprime nem copia `app.env` ou `db.env`.

Cada execução cria uma pasta nova, por exemplo:

```text
~/.local/share/investmind/backups/20261017T230000Z-1234abcd/
    database.dump
    metadata.json
```

A pasta tem permissão 700; os arquivos, 600. Essa localização fica fora do Git e
fora de pastas de cache. O dump contém dados do banco, inclusive hashes de senhas
e eventuais conversas de IA: mantenha-o privado e não envie o conteúdo ao chat.
Essas permissões controlam o acesso local; não são criptografia do arquivo.

`metadata.json` registra a versão da aplicação, a origem, o tamanho e o SHA256.
O SHA256 permite detectar alterações acidentais no dump. Não é uma assinatura
digital e não protege contra alguém que consiga alterar dump e metadados juntos.

Se houver erro durante a exportação, o arquivo parcial é descartado. O script
só anuncia o backup depois de receber um arquivo PostgreSQL e salvar metadados.
Ainda assim, exportar é apenas a primeira metade: execute a restauração real.

## 4. Restaurar em um banco temporário no Mac

Abra o Docker Desktop e execute:

```bash
python scripts/demo_database_backup.py verify latest
```

`latest` seleciona o backup completo mais recente nessa pasta do Mac. Para escolher
um backup específico, informe o caminho de `database.dump` no lugar de `latest`.
O script confere tamanho e SHA256 antes de iniciar qualquer container.

Usamos `pgvector/pgvector:0.8.7-pg18-bookworm`, a mesma imagem de banco definida
no deploy. Se ela não existir no Mac, o Docker precisará baixá-la uma vez.
O container de teste:

- tem nome aleatório próprio e rede `none`, sem portas publicadas;
- usa um banco novo chamado `restorecheck`, sem ligação aos bancos existentes;
- tem limite de 1 GB de memória e uma CPU, adequado ao pequeno banco de demonstração;
- recebe o dump pelo stdin, sem montar pastas do Mac;
- executa `pg_restore --single-transaction --exit-on-error --no-owner --no-privileges`;
- verifica a extensão vector, as migrations e a leitura das tabelas principais;
- é removido, com seus volumes anônimos, ao terminar ou se ocorrer uma falha tratável.

As restrições e os índices incluídos no dump são restaurados pelo PostgreSQL.
Os números mostrados são contagens no banco restaurado, não uma comparação com
o banco remoto naquele instante. A aplicação pode ter recebido novos registros
depois do início do dump.

O resultado esperado é:

```text
RESTORE TEST PASSED. The temporary database was removed.
```

A pasta do backup passa a conter `verification.json`, com data, imagem e contagens.
O dump original é mantido. O teste não altera a AWS nem o banco de desenvolvimento.
Ele comprova a restauração do banco; não inicia o Django nem testa login/IA no banco
temporário. O fluxo web já tem seus próprios testes e verificações de deploy.

Se o Docker parar ou o computador desligar à força, o cleanup pode não executar.
Identifique SOMENTE os containers criados por este teste:

```bash
docker ps -a --filter label=investmind.restore-check=true
```

Se algum tiver sobrado, remova seu ID específico com `docker rm -f -v ID_DO_TESTE`.
Não remova volumes ou containers do Compose do projeto para limpar esse teste.

## 5. Parar a EC2 e registrar o código

Depois que o comando `backup` terminar, a EC2 pode ser parada. O `verify` usa só o
Mac e funciona com a EC2 desligada. Use os comandos de parada do guia de operação.

Registre no Git somente os quatro arquivos desta entrega. O dump e os relatórios
locais ficam fora do repositório. Depois dos testes reais, faça commit, push e PR
de `feature/database-backup` para `develop`. A CI atual verifica a aplicação;
os testes desta ferramenta são executados pelo comando separado acima.

## Limites e recuperação de um incidente

Este é um backup lógico manual de UM banco, apropriado ao nosso demo pequeno.
Ele não é recuperação contínua/PITR. Não inclui roles do cluster, arquivos de
ambiente, chaves de API, chave Django, chave SSH, estado Terraform, uploads em disco
ou conteúdo pendente do Redis. Todos os dados presentes nas tabelas são exportados.

A restauração usa um novo usuário dono dos objetos; por isso `--no-owner` e
`--no-privileges` são opções da restauração. As contas Django e seus hashes fazem
parte das tabelas; os usuários/roles do PostgreSQL são uma camada diferente.

Em um incidente real, primeiro preparamos um destino novo, recuperamos o backup,
reconfiguramos segredos e validamos a aplicação antes de apontá-la ao banco recuperado.
Esse procedimento depende do destino e da versão de código escolhidos. Esta entrega
não implementa um comando que sobrescreve o banco da AWS.

Uma cópia no Mac já separa o backup da EC2. Ela ainda depende desse computador.
Para uma segunda cópia, use armazenamento privado com criptografia e preserve juntos
`database.dump`, `metadata.json` e, quando existente, `verification.json`.
Não há retenção ou exclusão automática: acompanhe o espaço ocupado e mantenha as
versões que precisar. Um teste não substitui verificar backups novos periodicamente.

## Referências

- https://www.postgresql.org/docs/18/app-pgdump.html
- https://www.postgresql.org/docs/18/app-pgrestore.html
- https://docs.docker.com/reference/cli/docker/container/run/
