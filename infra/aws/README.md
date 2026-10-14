# InvestMind AI: primeiro plano Terraform

## Objetivo desta entrega

Descrever um servidor de demonstração e revisar o plano antes de criar recursos.
Esta etapa termina em terraform plan. O servidor ainda não terá Docker, Ansible,
Django ou HTTPS instalados. Configurar o Linux e publicar a aplicação serão as
próximas etapas.

## Decisões

- Conta exclusiva: 990861495140; perfil investmind; região us-east-1.
- Instância Linux t4g.medium, ARM64, 2 vCPUs e 4 GiB de memória.
- Ubuntu 24.04 LTS de imagem oficial da Canonical.
- Disco gp3 criptografado, inicialmente 20 GB.
- Uma VPC própria, uma subnet pública e uma rota para a internet.
- HTTP/HTTPS públicos; SSH limitado ao seu IPv4 atual com /32.
- PostgreSQL e Redis terão apenas comunicação interna quando fizermos o deploy.
- Endereço IPv4 público automático: pode mudar ao parar e iniciar a EC2.
- CPU credits em modo standard: limita CPU sustentada quando os créditos
  acabam, evitando cobrança de créditos excedentes do modo unlimited.
- Sem NAT Gateway, load balancer ou Elastic IP reservado nesta entrega.
- O tamanho é um ponto inicial. Memória e desempenho serão verificados com a
  aplicação e tarefas reais; não foi feito teste de carga desse conjunto.
- A EC2 cobra enquanto está ligada. Parar somente containers não para a EC2.
- O disco cobra também com a EC2 parada. APIs de IA têm cobrança independente.

## Arquivos

| Arquivo | Função |
|---|---|
| versions.tf | Versões, provedor AWS, perfil e restrição do ID da conta |
| variables.tf | Chave pública SSH, IP permitido e tamanho do disco |
| main.tf | Rede, firewall, chave pública e EC2 |
| outputs.tf | ID, endereço e comando SSH após a criação |
| .gitignore | Exclui cache, estado, plano salvo e entradas locais |
| .dockerignore na raiz | Exclui esses dados do contexto da imagem Docker |
| scripts/prepare_terraform_demo.py | Prepara chave pública e IPv4 do Mac |
| scripts/estimate_aws_demo_cost.py | Consulta preços e calcula um subtotal |

HCL é a linguagem dos arquivos .tf. O provider traduz os recursos descritos
nesses arquivos em chamadas às APIs da AWS.

terraform init baixa o provider e gera .terraform.lock.hcl.
terraform fmt formata os arquivos.
terraform validate verifica a configuração.
terraform plan consulta a conta e mostra as mudanças propostas; não as executa.
terraform apply executará o plano em uma etapa posterior.

## Copiar a entrega

Na raiz de investmind-ai, depois de baixar e extrair o ZIP:

    unzip -n "$HOME/Downloads/InvestMind_Terraform_Demo.zip" -d "$HOME/Downloads"
    mkdir -p infra/aws scripts
    cp "$HOME/Downloads/InvestMind_Terraform_Demo/.dockerignore" .dockerignore
    cp -R "$HOME/Downloads/InvestMind_Terraform_Demo/infra/aws/." infra/aws/
    cp "$HOME/Downloads/InvestMind_Terraform_Demo/scripts/prepare_terraform_demo.py" scripts/
    cp "$HOME/Downloads/InvestMind_Terraform_Demo/scripts/estimate_aws_demo_cost.py" scripts/

A cópia de infra/aws/. inclui o .gitignore dessa pasta.
O .dockerignore completo preserva as exclusões anteriores e acrescenta as
exclusões do Terraform para impedir que estado, planos e entradas locais
sejam copiados para uma imagem Docker.

## Preparar a branch

Depois de integrar o PR de produção:

    git switch develop
    git pull --ff-only origin develop
    git status --short --branch

Se o status estiver limpo:

    git switch -c feature/aws-infrastructure

## Consultar o custo antes da criação

    aws sso login --profile investmind
    aws sts get-caller-identity --profile investmind --query Account --output text
    python scripts/estimate_aws_demo_cost.py --hours 20 --disk-gb 20

O ID precisa ser 990861495140. O script também confirma esse ID.
O estimador lê preços Linux On-Demand e EBS gp3 da API AWS Pricing, com os
filtros da região. Se não conseguir selecionar um preço único, interrompe o
cálculo em vez de assumir uma tarifa. O preço IPv4 está separado e usa a
tarifa pública de US$ 0,005/h.

O resultado é um subtotal de computação, disco e IPv4 para o cenário informado.
Não inclui impostos, câmbio, tráfego, backups, domínio e APIs de IA.
Ainda não há infraestrutura de backup nem domínio nesta entrega. Seus custos
serão somados antes do deploy. Se mudar o tamanho do disco, use o mesmo valor
no estimador e na entrada local root_volume_size_gb.

## Preparar o SSH e seu endereço

    python scripts/prepare_terraform_demo.py

O script cria ~/.ssh/investmind_demo se ainda não houver uma chave própria do
projeto. O ssh-keygen perguntará a passphrase: escolha uma e guarde-a.
A chave privada permanece fora do repositório. Só a chave pública é copiada.

A consulta a https://checkip.amazonaws.com identifica seu IPv4 público.
O arquivo infra/aws/local.auto.tfvars.json fica ignorado pelo Git.
Uma nova execução preserva outras entradas e atualiza chave pública e IP.
Se trocar de internet ou voltar à Itália, execute novamente e depois revise
o plano: normalmente apenas a regra SSH mudará.

## Inicializar e conferir

Execute a partir da raiz do repositório:

    terraform -chdir=infra/aws init
    terraform -chdir=infra/aws fmt
    terraform -chdir=infra/aws validate
    terraform -chdir=infra/aws plan

O Terraform 1.12.1 instalado é aceito pela configuração.
init escolhe um provider AWS da série 6 e grava sua versão no lock file.

No primeiro plano, confira:

- Conta: 990861495140.
- Região: us-east-1.
- Instância: t4g.medium.
- Arquitetura da imagem: arm64.
- Disco: gp3, criptografado, 20 GB.
- SSH: seu IP /32.
- Sem recursos para alterar ou remover.
- Expectativa: 12 recursos para adicionar, 0 para alterar, 0 para remover.

Envie a saída do estimador e o resumo do plano antes de executar apply.
Ainda não execute apply nesta etapa. Isso evita começar a cobrança antes de
revisar o custo e os recursos concretos.

Se o provider recusar a conta, mantenha a restrição allowed_account_ids.
Confira o perfil e as variáveis de ambiente de credenciais sem compartilhar
chaves, tokens ou arquivos de credenciais.

## Estado, Git e proteção dos dados

O estado Terraform é LOCAL nesta primeira etapa e fica em infra/aws.
Não é enviado ao Git. Depois da primeira criação, esse arquivo precisa de
uma cópia privada segura; antes do CI/CD de infraestrutura usaremos estado
remoto com bloqueio. Git guarda a receita e o lock file, não o estado real.

Commitar: .tf, README, .gitignore, .dockerignore, scripts e .terraform.lock.hcl.
Não commitar: .terraform/, .tfstate, planos salvos, local.auto.tfvars.json,
chaves privadas ou credenciais.

A instância tem prevent_destroy para bloquear remoção/substituição pelo
Terraform enquanto essa proteção estiver na configuração. Isso não bloqueia
exclusão manual pelo console. A AMI fica fora de alterações automáticas depois
da criação; atualizações do sistema serão tratadas na configuração do Linux.

STOP preserva este disco EBS e permite iniciar depois.
TERMINATE remove a instância e, nesta configuração, seu disco raiz.
Não use terraform destroy para desligar uma demonstração: o desligamento
normal será feito com stop-instances. Backup e restauração serão configurados
antes de usarmos dados importantes.

## Validação desta entrega

Scripts conferidos sintaticamente e com respostas simuladas.
Esta entrega não criou recursos na AWS. Terraform/provider e chamadas reais de
preço, imagem e plano precisam ser confirmados pelos comandos no Mac.
O plan não prova disponibilidade de capacidade EC2, acesso SSH ou execução
do Django: essas verificações ocorrem após criar e configurar o servidor.

## Referências

- https://developer.hashicorp.com/terraform/tutorials/aws-get-started/aws-create
- https://registry.terraform.io/providers/hashicorp/aws/latest/docs
- https://aws.amazon.com/ec2/instance-types/t4/
- https://aws.amazon.com/ebs/pricing/
- https://aws.amazon.com/vpc/pricing/
- https://docs.aws.amazon.com/cli/latest/reference/pricing/get-products.html
- https://ubuntu.com/aws/docs/aws-how-to/instances/find-ubuntu-images/
