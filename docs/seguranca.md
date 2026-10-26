# Segurança e privacidade local

- O servidor está limitado a 127.0.0.1. Não deve ser publicado em serviço web, túnel ou rede compartilhada.
- Host, Origin e nonce de sessão são conferidos nas operações de escrita. Código e dados privados não entram na lista de pastas servidas. Somente resultados, previews gerados e áudios importados podem ser acessados pela interface local.
- Outros programas e usuários com acesso ao computador podem ler arquivos locais conforme as permissões do sistema. Loopback e nonce não substituem isolamento do sistema operacional.
- Referência, transcrição, pesos, falas, vídeos, cache e planos reais ficam em `.local/`, fora do Git. Não use amostras ou vozes de terceiros sem autorização.
- O backend Qwen solicita arquivos locais e habilita os modos offline de Hugging Face/Transformers para inferência. A preparação inicial baixa pacotes e pesos públicos; não envia o áudio de referência.
- A senha OBS é digitada em terminal interativo, mantida em memória durante o processo e não é aceita por argumento de CLI. Logs do SDK são desabilitados. Não existe modo para desabilitar autenticação no OBS.
- O cliente OBS conecta apenas ao endpoint local. Configure o servidor OBS e o firewall para impedir exposição remota. Uma conexão local bem-sucedida não prova isolamento da rede.
- Prévia e revisão de áudio são responsabilidades do operador. A ferramenta não identifica automaticamente senhas, notificações ou dados pessoais na imagem capturada.
- O controlador recusa gravações já ativas e só encerra uma gravação que ele iniciou. Durante o comando, não troque a sessão de gravação manualmente. O original retornado pelo OBS é copiado, nunca movido ou sobrescrito.
- O auditor de release é uma barreira local de publicação, não uma certificação universal de ausência de segredos. Revise o conjunto versionado e o histórico antes de publicar. Arquivos ignorados não devem ser adicionados com `git add -f`.
