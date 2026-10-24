# InvestMind AI: preparar o servidor com Ansible

## O que esta etapa faz

O Terraform já criou rede, EC2 e disco. Agora o Ansible executa tarefas no
Ubuntu por SSH. O Mac é o controlador; a EC2 é o servidor administrado.
Ansible é instalado em um ambiente Python próprio no Mac. No servidor usamos
o Python do Ubuntu, sem instalar o pacote Ansible nem as dependências Django.

O playbook espera o cloud-init terminar, confirma Ubuntu 24.04 ARM64, instala
Docker Engine, Buildx e Compose pelo repositório oficial, configura rotação de
logs e habilita os serviços no boot. Cria /opt/investmind para o futuro deploy
e verifica Docker, Compose e a execução de hello-world.

Esta etapa não publica o InvestMind. Não há PostgreSQL, Redis, Django, HTTPS,
chaves de API ou envio de código para a EC2 ainda.

## Conceitos

- Inventário: informa os servidores, endereços e usuários a administrar.
- Playbook: arquivo YAML que organiza as tarefas.
- Task: uma tarefa, como instalar um pacote ou criar um diretório.
- Module: a operação usada pela tarefa, como apt, copy ou systemd_service.
- become: true: executar tarefas administrativas usando sudo no servidor.
- Handler: tarefa acionada quando uma configuração muda; aqui reinicia Docker.
- Idempotência: a execução repetida procura manter o estado desejado, sem
  reinstalar o que já está presente. Downloads e o teste temporário de
  hello-world ainda podem executar; cache APT e mudanças externas também podem
  causar alterações legítimas. Não usamos state: latest para atualizar Docker
  silenciosamente em toda execução.

## Arquivos

| Arquivo | Função |
|---|---|
| requirements.txt | Ansible Core 2.21.5 para o ambiente de ferramentas do Mac |
| prepare-server.yml | Tarefas executadas na EC2 |
| files/docker.sources | Fonte oficial de pacotes Docker, Ubuntu Noble ARM64 |
| files/daemon.json | Rotação de logs de novos containers |
| scripts/prepare_ansible_inventory.py | Consulta a AWS e prepara o inventário local |

O inventário gerado fica em ~/.config/investmind/ansible-inventory.json, fora
do Git e da imagem Docker. Ele contém o caminho da chave, nunca seu conteúdo.
As permissões do arquivo são 600. A chave privada continua em ~/.ssh.
Os arquivos existentes da aplicação e do Terraform permanecem como estão.

## 1. Branch e cópia

Na raiz do projeto no Mac, com o PR Terraform já integrado e status limpo:

    git switch develop
    git pull --ff-only origin develop
    git switch -c feature/ansible-server

Depois de baixar o ZIP:

    unzip -n "$HOME/Downloads/InvestMind_Ansible.zip" -d "$HOME/Downloads"
    mkdir -p infra/ansible scripts
    cp -R "$HOME/Downloads/InvestMind_Ansible/infra/ansible/." infra/ansible/
    cp "$HOME/Downloads/InvestMind_Ansible/scripts/prepare_ansible_inventory.py" scripts/

## 2. Instalar a ferramenta no Mac

Os comandos podem partir da .venv atual do projeto, mas criam outro ambiente
fora do repositório. Não adicionam Ansible ao requirements.txt do Django.

    python -m venv "$HOME/.venvs/investmind-ansible"
    "$HOME/.venvs/investmind-ansible/bin/python" -m pip install -r infra/ansible/requirements.txt
    "$HOME/.venvs/investmind-ansible/bin/ansible" --version

Ansible Core 2.21 aceita Python 3.12 a 3.14 no controlador; o Python 3.14
do projeto é compatível. O Ubuntu usa seu próprio /usr/bin/python3.
Se o terminal não tiver o comando python, ative primeiro a .venv habitual.

## 3. Renovar o acesso AWS e ligar a EC2

    aws sso login --profile investmind
    aws sts get-caller-identity --profile investmind --region us-east-1 --query Account --output text

O ID precisa ser 990861495140.

    aws ec2 start-instances --profile investmind --region us-east-1 --instance-ids i-0bb284d740d01bbd5 --no-cli-pager
    aws ec2 wait instance-status-ok --profile investmind --region us-east-1 --instance-ids i-0bb284d740d01bbd5

O segundo comando pode levar alguns minutos e não exibe progresso. Ele
aguarda as verificações da EC2. A partir do início, a máquina volta a cobrar.
Não use o IP antigo: ele pode mudar após parar e iniciar a instância.

## 4. Preparar o inventário e a chave SSH

    ssh-add "$HOME/.ssh/investmind_demo"
    python scripts/prepare_ansible_inventory.py

ssh-add pode pedir a passphrase escolhida para a chave. O ssh-agent permite
que Ansible use a chave sem pedir essa senha a cada tarefa. Se o agente não
estiver disponível, abra um terminal normal do macOS e tente novamente.

O script confirma conta, ID, VPC, tags, chave registrada e estado running,
consulta o IP atual na AWS e escreve o inventário. Ele não liga ou desliga
recursos, não altera Terraform e não lê o conteúdo da chave privada.

Ele também mostra fingerprints já confiadas pelo Mac para o IP atual ou para
o IP anterior registrado no state Terraform. Execute este passo ANTES do novo
plan/apply abaixo, para ainda poder usar a referência anterior. Guarde essa
saída para a comparação do passo 5. O inventário usa o IP atual consultado na
AWS, mesmo que o IP registrado no state ainda seja antigo.

## 5. Atualizar a regra SSH e confirmar a conexão

    python scripts/prepare_terraform_demo.py
    terraform -chdir=infra/aws plan -input=false -out=ansible-access.tfplan

Se não houver mudanças de recursos, não é necessário aplicar esse plano para
executar Ansible: o inventário já tem o IP atual. O plano pode mostrar apenas
atualização dos outputs após a troca do endereço público.
Se seu IPv4 mudou, é esperado substituir somente a regra SSH:
aws_vpc_security_group_ingress_rule.ssh. Isso pode aparecer como 1 recurso
adicionado e 1 removido; a instância e o disco precisam permanecer intactos.
Se houver qualquer mudança fora dessa regra, revise a saída antes de aplicar.

Somente se o plano ajustar essa regra ou apenas atualizar outputs:

    terraform -chdir=infra/aws apply ansible-access.tfplan

O helper apenas prepara o arquivo; quem muda a regra na AWS é o apply.
Repetir esta preparação será útil ao trocar de rede ou de país.

Agora execute o comando SSH que o script do passo 4 imprimiu. Se houver uma
pergunta sobre a autenticidade do servidor, compare a fingerprint SHA256 com
as fingerprints já confiadas pelo Mac mostradas naquele passo. Elas são
extraídas do known_hosts.

Essa comparação pressupõe a mesma instância, que acabamos de criar e verificar.
Se o script não encontrar uma referência já confiada, ele imprime o comando
AWS get-console-output. Procure BEGIN SSH HOST KEY FINGERPRINTS nessa saída e
compare a identificação do mesmo tipo (normalmente ED25519). Caso não encontre
uma referência ou haja divergência, investigue antes de aceitar. Não remova
chaves antigas nem desative a verificação para contornar um aviso.

Depois de conectar, digite exit para voltar ao Mac.

## 6. Validar e executar a configuração

Todos estes comandos são executados NO MAC, na raiz do projeto:

    "$HOME/.venvs/investmind-ansible/bin/ansible-playbook" -i "$HOME/.config/investmind/ansible-inventory.json" infra/ansible/prepare-server.yml --syntax-check
    "$HOME/.venvs/investmind-ansible/bin/ansible" -i "$HOME/.config/investmind/ansible-inventory.json" investmind -m ansible.builtin.ping
    "$HOME/.venvs/investmind-ansible/bin/ansible-playbook" -i "$HOME/.config/investmind/ansible-inventory.json" infra/ansible/prepare-server.yml --diff

syntax-check verifica o playbook sem alterar o servidor. O módulo ping confirma
SSH e Python; é diferente de um ping ICMP de rede. O último comando instala e
configura os programas na EC2. --diff mostra diferenças dos arquivos gerenciados.
Não há necessidade de entrar por SSH e copiar os comandos de instalação.

O playbook usa sudo e não adiciona ubuntu ao grupo docker. Em um terminal SSH,
use sudo docker para comandos que acessam o daemon. Não instalamos Docker
Desktop e não é necessário login no Docker Hub para esta instalação.

A configuração do daemon usa o driver de logs local, com rotação de até três
arquivos de 10 MB por container. Ela vale para containers novos. Logs do sistema
e o restante do disco não são limitados por essa configuração.

## 7. Verificar uma segunda execução

    "$HOME/.venvs/investmind-ansible/bin/ansible-playbook" -i "$HOME/.config/investmind/ansible-inventory.json" infra/ansible/prepare-server.yml --diff

Em uma repetição imediata, sem mudanças externas, esperamos failed=0,
unreachable=0 e changed=0. Se houver alterações, leia quais tarefas mudaram.
O teste hello-world cria e remove um container temporário; o primeiro download
da imagem é contado como alteração. O playbook não apaga imagens ou volumes.
Mudanças futuras em daemon.json podem reiniciar Docker; planeje essa operação
quando já houver uma aplicação em execução.

## 8. Desligar após terminar

De volta ao Mac:

    aws ec2 stop-instances --profile investmind --region us-east-1 --instance-ids i-0bb284d740d01bbd5 --no-cli-pager
    aws ec2 wait instance-stopped --profile investmind --region us-east-1 --instance-ids i-0bb284d740d01bbd5

Sair do SSH não desliga a máquina. Stop preserva o disco e os programas
instalados; o disco EBS continua cobrando. Não use terminate ou terraform destroy.
O diretório /opt/investmind estará vazio até fazermos o deploy da aplicação.

## Git e validação

Após a execução real, conferir git status e adicionar somente infra/ansible e
scripts/prepare_ansible_inventory.py. O state Terraform, planos e entradas locais
continuam ignorados; o inventário foi criado fora do repositório.
O CI atual do projeto continua verificando Docker/Django; esta entrega não
adiciona um job Ansible ao GitHub. O resultado real na EC2 é verificado pelo
playbook e deve ser conferido antes do commit.

Sintaxe e módulos são conferidos com Ansible Core 2.21.5 nesta entrega. O helper
é verificado com respostas AWS simuladas, incluindo IP atualizado, conta errada
e instância parada. Isso não substitui instalar e testar na sua EC2 ARM64; essa
verificação acontece seguindo os passos acima. Nenhum recurso AWS foi acessado
ou modificado na preparação dos arquivos.

## Referências

- https://docs.docker.com/engine/install/ubuntu/
- https://docs.docker.com/engine/logging/drivers/local/
- https://docs.ansible.com/projects/ansible/latest/intro_installation.html
- https://docs.ansible.com/projects/ansible/latest/reference_appendices/release_and_maintenance.html
- https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/ssh_connection.html
