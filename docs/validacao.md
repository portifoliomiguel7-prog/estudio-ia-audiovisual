# Validação da versão pública — 26/10/2026

Executada no Windows com Python 3.13.7 para servidor, montagem e testes básicos. O teste de clonagem reutilizou um ambiente Python 3.12 já instalado, os pesos oficiais em cache e uma referência privada previamente autorizada. A referência e os resultados de áudio/vídeo não fazem parte da publicação.

## Instalação e testes

Uma venv nova instalou `requirements.txt` e `requirements-obs.txt`. `python -m pip check` retornou:

```text
No broken requirements found.
```

`python -m unittest discover -s tests -v` executou 16 testes: 15 passaram e um foi explicitamente ignorado porque a conta Windows não permite criar links simbólicos. Não foi contado como teste aprovado. O caso cobre rejeição de symlink; os demais casos de contenção de caminhos foram executados.

```text
Ran 16 tests
OK (skipped=1)
```

Cobertura: Host/Origin/nonce, gravação concorrente, bloqueio HTTP de código/raw/referência/modelo, traversal, montagem com dois vídeos de teste, decodificação, fonte preservada, áudio fora da janela rejeitado, IDs de cena superiores a sete, consentimento exigido e guarda OBS para não interromper gravação existente. Os testes OBS usam um cliente simulado; nenhum comando StartRecord foi enviado ao OBS real neste teste de release.

## Síntese e montagem executadas

Além da suíte, o estúdio importou um vídeo de teste de 12 segundos, sintetizou duas falas pela voz Windows e montou o MP4 completo. Decodificação integral PASS. SHA256 do fluxo de vídeo copiado e hash do arquivo de origem foram conferidos: imagem e original preservados.

O backend público `voice_clone.py` gerou uma fala curta real com Qwen3-TTS em CPU, sem baixar novamente o modelo e sem enviar a referência para outro serviço:

```json
{
  "duration_seconds": 4.16,
  "sample_rate": 24000,
  "generated_tokens": 52,
  "token_limit": 256,
  "hit_token_limit": false,
  "decode": "PASS"
}
```

Essa medição prova geração e decodificação no ambiente reutilizado. Não é uma nova instalação completa das dependências de voz, avaliação de similaridade por terceiros ou aprovação de naturalidade. Os pacotes básicos e do controlador OBS tiveram instalação nova; as dependências grandes de clonagem foram reutilizadas.

## Limites

- As fixtures audiovisuais da suíte são sintéticas e existem apenas para testar software. Não demonstram execução do pipeline DIO.
- O controlador OBS desta edição foi validado com cliente simulado e assinatura do SDK instalado. Conexão autenticada, prévia e captura reais precisam ser conferidas pelo operador em seu OBS.
- Os testes locais de Windows não qualificam a síntese SAPI em outros sistemas. SAPI requer Windows e uma voz instalada. A montagem com áudio importado não depende do SAPI.
- A variante Qwen foi testada em CPU, sem FlashAttention. Não foi avaliado o caminho GPU desta versão.
- O script de download deriva do protótipo com revisão e SHA256 LFS, mas o download de todos os pesos não foi repetido neste teste de release.
- O servidor não foi preparado para hospedagem pública. Referências, pesos, saídas e configurações reais permanecem privados e ignorados pelo Git.
- Não houve nova operação Confluent/Neon, nova gravação do laboratório ou contratação de serviço.

Uma auditoria final usa a allowlist explícita em `audit_release.py`, padrões locais e comparação em memória com valores privados conhecidos no ambiente do autor. Ela não substitui revisão de segurança abrangente nem garante detecção de todos os segredos possíveis.
