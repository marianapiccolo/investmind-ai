# Operação do demo InvestMind AI

Todos os comandos deste guia são executados no terminal do MAC, dentro do projeto.
O único `exit` indicado abaixo é executado dentro da sessão SSH recém-aberta.

## Preparação local

```bash
cd ~/Documentos/GitHub/investmind-ai
source .venv/bin/activate
aws sso login --profile investmind
aws sts get-caller-identity --profile investmind --region us-east-1 --query Account --output text --no-cli-pager
```

A conta esperada é `990861495140`. Se aparecer outra, interrompa antes de executar
operações de EC2. Não use os perfis default/dev-ops do projeto CloseBills.

## Consultar o estado

```bash
aws ec2 describe-instances --profile investmind --region us-east-1 --instance-ids i-0bb284d740d01bbd5 --query 'Reservations[0].Instances[0].State.Name' --output text --no-cli-pager
```

## Ligar e aguardar

Se estiver `stopped`:

```bash
aws ec2 start-instances --profile investmind --region us-east-1 --instance-ids i-0bb284d740d01bbd5 --no-cli-pager
aws ec2 wait instance-status-ok --profile investmind --region us-east-1 --instance-ids i-0bb284d740d01bbd5
```

O waiter pode ficar sem mensagens enquanto aguarda os checks da instância.

## Atualizar acesso SSH

```bash
python scripts/prepare_terraform_demo.py
python scripts/prepare_ansible_inventory.py
terraform -chdir=infra/aws plan -input=false -out=demo-access.tfplan
```

O inventário deve ser preparado ANTES de atualizar o estado Terraform: ele consulta
o IP real e pode usar o IP anterior do estado para encontrar a chave do host já
confiada pelo Mac. O outro helper atualiza o seu IPv4/32 para a regra SSH.

Se o plano só atualizar outputs e/ou a regra SSH para seu IPv4/32:

```bash
terraform -chdir=infra/aws apply demo-access.tfplan
```

Se houver substituição da EC2, exclusão de disco ou mudanças fora desse acesso,
revise o plano antes de aplicar. Preserve o estado Terraform e o arquivo de chave.

Execute o comando SSH impresso pelo inventário. Para um IP novo, compare a chave
do host com a referência já confiada. A chave conhecida desta EC2 é:

```text
SHA256:80v5mPhAYqFx/I7Pwc6o939ynHtmHUVcz+pYu4V/mQQ
```

Uma futura substituição legítima da EC2 pode mudar essa chave e exigirá nova
verificação na AWS. Não aceite uma diferença só porque apareceu um IP novo.
Depois de conectar, execute `exit` para voltar ao terminal do Mac.

## Somente fazer backup

```bash
python scripts/demo_database_backup.py backup
```

O script encontra o IP atual pela AWS e exige a chave do host já confiada.
Não precisa de HTTPS nem de deploy para essa exportação.
Quando o backup terminar, você já pode parar a EC2 e restaurar no Mac:

```bash
python scripts/demo_database_backup.py verify latest
```

## Apresentar a aplicação pelo navegador

O fluxo atual usa uma imagem publicada pelo GitHub Actions no GHCR privado.
Na primeira vez, siga `docs/registry-delivery.md` para baixar e selecionar o
artifact da versão publicada. O checkout local deve corresponder a esse commit.
Com a release já preparada e o SSH atualizado:

```bash
ssh-add "$HOME/.ssh/investmind_demo"
python scripts/deploy_registry_demo.py
```

O script pede um token GitHub classic com `read:packages` sem exibi-lo.
Ansible faz a EC2 baixar a imagem por digest, atualiza IP/HTTPS e verifica os serviços.
Use a URL impressa ao terminar. Teste login, carteira, compra/venda e os recursos
IA/cotações que pretende mostrar. Prepare o demo antes da entrevista para ter
tempo de renovar certificados, conferir dados e resolver provedores externos.

## Publicar outra versão do código

Valide as mudanças, faça commit/push/PR e aguarde CI verde. Depois do merge em
develop ou main, a CI constrói, verifica e publica a imagem ARM64 no GHCR.
Atualize seu checkout local e selecione o artifact dessa execução conforme
`docs/registry-delivery.md`. Depois execute o seletor acima para implantar.
A publicação da imagem não liga nem atualiza automaticamente a EC2.

Para mudanças com migrations, faça um backup antes do deploy. Um rollback de
imagem não desfaz migrations nem recupera registros.

## Alternativa: build e transferência pelo Mac

O fluxo original continua disponível:

```bash
python scripts/build_demo_release.py
"$HOME/.venvs/investmind-ansible/bin/ansible-playbook" -i "$HOME/.config/investmind/ansible-inventory.json" infra/ansible/deploy-demo.yml
```

Esse fluxo usa `~/.cache/investmind/release.json`, enquanto o registry usa
`registry-release.json`. Confira qual versão está selecionada em cada fluxo;
uma nova execução do build local não muda os metadados do registry, e vice-versa.

## Parar e confirmar

De volta ao terminal do Mac:

```bash
aws ec2 stop-instances --profile investmind --region us-east-1 --instance-ids i-0bb284d740d01bbd5 --no-cli-pager
aws ec2 wait instance-stopped --profile investmind --region us-east-1 --instance-ids i-0bb284d740d01bbd5
aws ec2 describe-instances --profile investmind --region us-east-1 --instance-ids i-0bb284d740d01bbd5 --query 'Reservations[0].Instances[0].State.Name' --output text --no-cli-pager
```

O resultado deve ser `stopped`. Fechar navegador, encerrar SSH ou desligar o Mac
não para a EC2. O disco é mantido ao parar; os dados e o backup têm ciclos distintos.
O custo do armazenamento mantido permanece conforme a estimativa do projeto.
