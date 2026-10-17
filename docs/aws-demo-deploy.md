# InvestMind AI: primeiro deploy público na EC2

## O que vamos colocar no servidor

A imagem de produção já foi testada no Mac e no CI. Esta etapa constrói uma
versão COMMITADA da aplicação para Linux ARM64 no Mac e a transfere por SSH.
Ansible carrega a imagem na EC2, prepara variáveis, inicia PostgreSQL e Redis,
aplica migrations e inicia Django/Gunicorn, Celery Worker, Celery Beat e Caddy.

O navegador acessa Caddy por HTTPS na porta 443. Caddy encaminha a requisição
para web:8000. Só Caddy publica portas no host. PostgreSQL e Redis não publicam
portas. Os serviços de aplicação usam redes Docker para comunicação interna.
Usamos as configurações estritas de produção: DEBUG=False, cookies seguros,
redirecionamento HTTPS e cabeçalho de proxy controlado pelo Caddy.

O banco da AWS é NOVO e separado do banco local. Usuários, carteiras e dados
do Mac não são copiados. Criaremos um superuser novo depois da implantação.
O diretório /opt/investmind/current aponta para a versão que passou nos testes.

## HTTPS sem comprar domínio

O endereço será https://IP_PUBLICO_ATUAL/. Caddy solicita um certificado
Let’s Encrypt para esse IP usando o perfil shortlived e o renova enquanto
o servidor está funcionando. O default_sni evita selecionar o IP privado
do container quando o navegador acessa um IP sem enviar SNI.

Os certificados de IP duram aproximadamente seis dias. Depois de semanas
com a EC2 parada, ao ligar novamente pode ser necessário aguardar a emissão
de um certificado novo. Se o IP mudou, execute novamente o inventário e o
playbook de deploy, que atualiza os hosts Django, CSRF e o proxy. Não basta
substituir o IP na barra do navegador, porque a configuração anterior precisa
ser atualizada. Não use --insecure ou aceite certificados inválidos no navegador.

Esta configuração não compra domínio, reserva Elastic IP ou cria load balancer.
Os custos EC2, IPv4, EBS, tráfego e eventuais chamadas de API continuam existindo.
Imagens, arquivos exportados e volumes ocupam espaço no disco; não estamos
configurando retenção automática de versões nem backup remoto nesta etapa.

## 1. Branch e arquivos (Mac)

Com o PR Ansible integrado e o repositório limpo:

    cd ~/Documentos/GitHub/investmind-ai
    git switch develop
    git pull --ff-only origin develop
    git status --short --branch
    git switch -c feature/aws-demo-deploy

Depois de baixar o ZIP:

    unzip -n "$HOME/Downloads/InvestMind_AWS_Deploy.zip" -d "$HOME/Downloads"
    mkdir -p docker/caddy docker/postgres infra/ansible scripts docs
    cp "$HOME/Downloads/InvestMind_AWS_Deploy/compose.production.yaml" .
    cp "$HOME/Downloads/InvestMind_AWS_Deploy/docker/caddy/Caddyfile" docker/caddy/
    cp "$HOME/Downloads/InvestMind_AWS_Deploy/docker/postgres/init-vector.sql" docker/postgres/
    cp "$HOME/Downloads/InvestMind_AWS_Deploy/infra/ansible/deploy-demo.yml" infra/ansible/
    cp "$HOME/Downloads/InvestMind_AWS_Deploy/scripts/build_demo_release.py" scripts/
    cp "$HOME/Downloads/InvestMind_AWS_Deploy/scripts/manage_demo_env.py" scripts/
    cp "$HOME/Downloads/InvestMind_AWS_Deploy/docs/aws-demo-deploy.md" docs/

O SQL é o mesmo da infraestrutura local e é incluído para completar a entrega.
Os arquivos anteriores de Docker, Django e Ansible permanecem como estão.

## 2. Construir a versão no Mac antes de ligar a EC2

Abra Docker Desktop. Na .venv habitual do projeto:

    python scripts/build_demo_release.py

O script usa git archive HEAD: somente a versão commitada entra na imagem.
Se houver alterações em arquivos rastreados, interrompe e pede revisão. Os
novos arquivos de implantação podem estar untracked, porque são copiados
separadamente pelo Ansible e não são necessários dentro da imagem Django.
Alterações de funcionalidades Python precisam ser commitadas antes do build.

O build usa Dockerfile.production e --platform linux/arm64. A imagem recebe
uma tag com o SHA do commit. O arquivo comprimido e release.json ficam em
~/.cache/investmind, fora do Git. A imagem não é publicada em um registry.
O Ansible verifica o SHA256 do arquivo e a identidade da imagem após o envio.

Na primeira construção pode demorar vários minutos. A EC2 ainda pode ficar
parada durante essa parte. O script não acessa a AWS nem copia o .env do Mac.

## 3. Ligar a máquina e preparar o acesso (Mac)

    aws sso login --profile investmind
    aws sts get-caller-identity --profile investmind --region us-east-1 --query Account --output text

Confirme 990861495140.

    aws ec2 start-instances --profile investmind --region us-east-1 --instance-ids i-0bb284d740d01bbd5 --no-cli-pager
    aws ec2 wait instance-status-ok --profile investmind --region us-east-1 --instance-ids i-0bb284d740d01bbd5
    ssh-add "$HOME/.ssh/investmind_demo"
    python scripts/prepare_ansible_inventory.py

Guarde a saída com o IP e as fingerprints já confiadas pelo Mac. O script
consulta a AWS para pegar o endereço atual, não o IP antigo do Terraform.

    python scripts/prepare_terraform_demo.py
    terraform -chdir=infra/aws plan -input=false -out=deploy-access.tfplan

Sem mudanças, continue. Se houver somente atualização dos outputs ou da regra
aws_vpc_security_group_ingress_rule.ssh para seu IP /32, aplique:

    terraform -chdir=infra/aws apply deploy-access.tfplan

Se houver alteração em EC2, disco ou outros recursos, revise antes de aplicar.

Execute o comando SSH impresso pelo inventário. Se o IP for novo, compare a
fingerprint do aviso com a identificação já confiada apresentada pelo script.
Se a referência estiver ausente, use a consulta AWS que o helper imprime para
conferir a fingerprint. Não desative a validação SSH para contornar divergências.
Depois de conectar, digite exit para voltar ao Mac.

## 4. Implantar (comandos executados no Mac)

    "$HOME/.venvs/investmind-ansible/bin/ansible-playbook" -i "$HOME/.config/investmind/ansible-inventory.json" infra/ansible/deploy-demo.yml --syntax-check
    "$HOME/.venvs/investmind-ansible/bin/ansible-playbook" -i "$HOME/.config/investmind/ansible-inventory.json" infra/ansible/deploy-demo.yml

Este é um playbook de DEPLOY. Ele faz download de imagens de infraestrutura,
para processos da aplicação durante migrations e inicia a versão selecionada.
Uma nova execução pode registrar changed>0 mesmo sem mudança no código. O
teste changed=0 pertence ao prepare-server.yml, não a este fluxo de implantação.
O deploy simples tem uma janela de indisponibilidade; alta disponibilidade
e migração sem downtime não fazem parte desse ambiente de demonstração.

O primeiro envio do arquivo comprimido pode demorar. Após iniciar Caddy, o
teste HTTPS pode repetir por alguns minutos enquanto o certificado é emitido.
O teste usa curl no Mac, com verificação de certificado ativa. Isso evita o
problema anterior do repositório de certificados do Python local.

Ao concluir, envie o PLAY RECAP e o endereço público apresentado. O teste
confere HTTPS, admin, CSS e conexão do Worker ao Redis. Ainda precisamos
testar as funcionalidades reais e os provedores externos depois do login.

## 5. Criar o usuário (comandos executados DENTRO da EC2)

Conecte novamente com o comando SSH impresso pelo helper. No terminal ubuntu@:

    sudo docker compose --env-file /opt/investmind/shared/deployment.env --file /opt/investmind/current/compose.production.yaml exec web python manage.py createsuperuser

Escolha usuário, email e uma senha forte. A senha não aparece ao digitar.
O banco da AWS não possui o usuário do Mac; ele precisa ser criado aqui.
Abra https://IP_ATUAL/admin/ no navegador. O certificado precisa ser válido.
Teste também a página de login e o dashboard do projeto, criando dados fictícios
de demonstração pelo fluxo da aplicação. Não importamos o banco local.

## 6. Informar chaves de API sem enviá-las ao chat ou ao Git (EC2)

As senhas PostgreSQL e a chave Django foram geradas na EC2. Os arquivos
/opt/investmind/shared/app.env e db.env têm permissões 600 e pertencem a root.
Eles ficam fora das pastas de releases e são preservados nas novas execuções.
A aplicação recebe variáveis de produção; o modo local de teste está desligado.

Na primeira criação as chaves OpenAI e Alpha Vantage ficam vazias. O deploy
da infraestrutura funciona sem elas, mas os recursos que usam esses provedores
precisam das suas chaves válidas. Para informá-las, dentro da EC2:

    sudo python3 /opt/investmind/bin/manage_demo_env.py --configure-apis

O script pede as chaves sem exibi-las e mantém um valor existente se você
pressionar Enter. Ele não gera nem troca chaves dos provedores e não faz chamadas
às APIs. Depois recrie somente os processos que precisam reler o ambiente:

    sudo docker compose --env-file /opt/investmind/shared/deployment.env --file /opt/investmind/current/compose.production.yaml up -d --no-deps --force-recreate --wait --wait-timeout 180 web worker beat

Então teste cotações, processamento em segundo plano e IA com uma carteira de
demonstração. Esses testes reais podem consumir as cotas/créditos dos provedores.
O modelo OpenAI é o definido no código commitado, a menos que você configure
OPENAI_MODEL no app.env. Configuração e envio real de email SMTP ficam pendentes.

## 7. Verificar e investigar problemas (EC2)

    sudo docker compose --env-file /opt/investmind/shared/deployment.env --file /opt/investmind/current/compose.production.yaml ps
    sudo docker compose --env-file /opt/investmind/shared/deployment.env --file /opt/investmind/current/compose.production.yaml logs --tail=80 web worker beat proxy
    sudo docker stats --no-stream
    df -h /

Se o deploy falhar antes de criar o link current, use --file com o diretório
/opt/investmind/releases/SHA_DO_COMMIT/compose.production.yaml, informado no build.
Compartilhe somente o erro relevante e remova eventuais dados pessoais. Não
execute compose config sem --quiet: a saída pode mostrar variáveis secretas.
Não compartilhe app.env, db.env, chaves privadas ou arquivos de credenciais.

O armazenamento usa volumes nomeados do projeto investmind-ai-demo, que
permanecem após stop/start e troca de release. Não use down --volumes: isso
remove os dados. Docker volumes são persistência, não backup. Terminando a EC2,
o disco raiz e os dados nela serão removidos conforme nosso Terraform.

## 8. Parar e voltar a usar

Dentro da EC2, use exit. De volta ao Mac:

    aws ec2 stop-instances --profile investmind --region us-east-1 --instance-ids i-0bb284d740d01bbd5 --no-cli-pager
    aws ec2 wait instance-stopped --profile investmind --region us-east-1 --instance-ids i-0bb284d740d01bbd5

O disco continua cobrando. Para outra apresentação, repita os passos 3 e 4 para
atualizar o IP no inventário e na aplicação. Reutilize a imagem já construída;
execute o passo 2 novamente quando quiser implantar outro commit. A URL poderá
mudar. Prepare e teste o acesso antes da entrevista para aguardar eventual
emissão/renovação de certificado e confirmar login, dados e serviços externos.

## O que ainda vem depois

Este primeiro deploy é manual e não altera o workflow CI existente. Depois
verificaremos backup/restauração, operação de start/stop e demonstração, e
automatizaremos a entrega de imagens/versões pelo GitHub Actions. O código
guarda versões; rollback de código não desfaz automaticamente migrations nem
restaura dados. Não executamos rollback automático nesta entrega.

Esta entrega teve verificações locais de sintaxe, parâmetros dos módulos,
Compose, Caddy e testes do gerador de ambiente. Sem seu checkout completo ou
acesso à sua AWS, não é possível executar a aplicação real ou emitir seu
certificado daqui. A validação ponta a ponta será feita pelos comandos acima.

## Referências

- https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability/
- https://caddyserver.com/docs/caddyfile/directives/tls
- https://caddyserver.com/docs/caddyfile/options
- https://docs.docker.com/reference/compose-file/services/
- https://docs.docker.com/reference/cli/docker/image/save/
- https://docs.docker.com/reference/cli/docker/image/load/
