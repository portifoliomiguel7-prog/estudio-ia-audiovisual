# Estúdio IA Audiovisual

Uma ferramenta local para transformar roteiro em narração e organizar a voz junto de vídeos já gravados. Também inclui um controlador do OBS para consultar a cena, obter uma prévia e gravar um trecho com duração definida.

Nasceu como apoio à apresentação de um [projeto DIO de pagamentos em tempo real](https://github.com/portifoliomiguel7-prog/desafio-final-kafka-publico). Esta versão foi separada do laboratório para outras pessoas poderem usar os próprios vídeos e uma voz própria ou autorizada.

## O que faz

- Importa vídeos sem alterar os originais e mede a duração com FFmpeg.
- Permite editar o roteiro e o início de cada fala no navegador.
- Gera voz com o Windows ou, opcionalmente, clona uma referência autorizada com Qwen3-TTS local.
- Aceita WAV externo na montagem, inclusive sem instalar o modelo de voz.
- Reutiliza falas em cache, recusa sobreposição e gera cenas narradas e um vídeo completo.
- Decodifica os vídeos produzidos e registra hashes dos arquivos de origem.
- Consulta e controla o OBS pelo WebSocket local, com senha digitada de forma privada.

O modelo de voz é o [Qwen3-TTS-12Hz-0.6B-Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base), não um modelo treinado do zero neste projeto. A montagem e o controle do OBS são automação. A navegação original do laboratório foi conduzida com assistência do Codex; este repositório não contém o Codex, sua extensão ou um agente autônomo de navegação na Confluent. [Contexto e limites](docs/transparencia.md).

## Começar no Windows

Recomendado: Python 3.12, Git e Windows com uma voz PT-BR instalada. A instalação básica não baixa os pesos de IA e não precisa de conta cloud.

```powershell
git clone https://github.com/portifoliomiguel7-prog/estudio-ia-audiovisual.git
cd estudio-ia-audiovisual
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe project.py --video "C:\Videos\minha-cena.mp4"
.\.venv\Scripts\python.exe studio.py --serve --open
```

Se Python já estiver no PATH, `python -m venv .venv` também pode ser usado. A montagem e o servidor foram testados com Python 3.13; para o ambiente de clonagem validado, use Python 3.12. Não é necessário ativar o ambiente: os comandos acima chamam diretamente o executável da venv. Depois de instalar, `Abrir-estudio.cmd` abre o servidor no Windows.

O terminal imprime um endereço `http://127.0.0.1:PORTA`. No navegador, escolha uma voz disponível, edite o texto e os tempos, salve e gere uma cena antes de gerar tudo. O texto inicial de importação é apenas um exemplo: substitua-o pelo seu roteiro.

Para importar outra cena, feche o estúdio, repita `project.py --video CAMINHO` e abra novamente. O programa preserva o plano existente e acrescenta a nova cena. Recarregue a página se tiver alterado o plano pelo terminal. Consulte [o exemplo de plano](examples/plan.example.json).

## Sua voz, localmente — opcional

Use somente a própria voz ou uma referência cujo uso foi autorizado. Nenhuma amostra pessoal acompanha este repositório. Prepare um trecho limpo, sem música e sem outras pessoas falando. Ouça o resultado antes de usá-lo publicamente.

Na mesma venv Python 3.12:

```powershell
.\.venv\Scripts\python.exe -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements-voice.txt
.\.venv\Scripts\python.exe download_model.py
.\.venv\Scripts\python.exe prepare_reference.py --audio "C:\Audios\minha-voz.wav" --start 0 --seconds 12 --consent
.\.venv\Scripts\python.exe studio.py --serve --open
```

O download usa o repositório oficial Qwen no Hugging Face, fixado em uma revisão. São aproximadamente 2,5 GB de pesos, fora das dependências. Arquivos LFS são conferidos por SHA256. A inferência usa somente os pesos locais, em CPU/float32, com modos offline das bibliotecas habilitados. Ela não envia a referência para um provedor. Downloads iniciais de pacotes e modelo precisam de internet.

No estúdio, faça um teste curto antes de selecionar **Minha voz (clone local)** para as cenas. O preparo da referência não é uma aprovação de qualidade. Sem transcrição da referência, o backend usa `x_vector_only`; uma transcrição exata pode ser colocada privadamente em `.local/studio/voice-clone/private/reference.txt`. Não invente o texto. A versão Base não oferece aqui controle de emoção por instruções: pontuação e roteiro ajudam, mas não garantem interpretação humana.

O arquivo [requirements-voice-tested.txt](requirements-voice-tested.txt) registra o ambiente CPU utilizado no protótipo. É um registro de versões testadas, não uma promessa de compatibilidade com qualquer sistema. Geração em CPU pode levar vários minutos por cena e consumir vários GB de RAM.

## Montar com áudio externo

Copie um WAV próprio/autorizado para `.local/studio/imports/`. No campo de áudio externo da fala, informe somente o caminho relativo, por exemplo `narracao.wav`. Esse bloco usa o áudio informado, sem sintetizar outra voz.

Os tempos são manuais, por blocos. A ferramenta preserva a velocidade do vídeo e recusa uma fala que não caiba na janela; não corta a fala nem usa alinhamento automático por palavra. Ajuste texto e horários conforme a mensagem de erro. O áudio original do vídeo não entra na montagem narrada. O vídeo é copiado sem recodificação; use MKV/MP4 com H.264 para o fluxo testado. MOV e outros codecs podem ser importados, mas nem todos são compatíveis com o remux para MP4.

## Gravar com OBS — opcional

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-obs.txt
.\.venv\Scripts\python.exe obs_control.py status
.\.venv\Scripts\python.exe obs_control.py preview
```

No OBS 28+, habilite o WebSocket com autenticação. O cliente usa somente `127.0.0.1:4455`; uma regra de firewall/bind apropriada deve impedir acesso externo ao servidor OBS. O cliente local não verifica por si só a exposição da porta na rede. A senha é solicitada com `getpass` em terminal interativo, sem argumento de linha de comando ou arquivo de configuração.

Abra a prévia gerada e confira o mixer, o monitor capturado e a ausência de dados privados. Depois, para gravar 20 segundos enquanto você navega:

```powershell
.\.venv\Scripts\python.exe obs_control.py record --seconds 20 --preview-reviewed --audio-reviewed
```

Essas flags registram sua confirmação de revisão; não fazem uma inspeção visual automática nem silenciam o mixer. O comando recusa gravação já existente, inicia uma gravação própria, encerra ao fim do período, decodifica e copia o arquivo retornado pelo OBS. O original fica preservado. Não interaja com iniciar/parar gravação durante esse comando. [Detalhes de segurança](docs/seguranca.md).

## Dados e configuração

Por padrão, entradas, voz, cache, modelos e resultados ficam em `.local/studio/`, ignorada pelo Git. O servidor escuta somente em loopback e não serve `raw/`, referências de voz, modelo, código ou `.git`. O índice e a API local usam um nonce de sessão para mutações, além da conferência de Host/Origin. Não exponha esse servidor em túnel ou hospedagem pública.

Variáveis opcionais do processo:

| Variável | Uso |
|---|---|
| `STUDIO_WORKSPACE` | Outra pasta de trabalho, separada do código; útil para manter projetos e vozes separados. |
| `FFMPEG_BINARY` | Caminho para FFmpeg existente; caso ausente, usa PATH ou o binário de imageio-ffmpeg. |
| `QWEN_MODEL_DIR` | Reutilizar um modelo já baixado, sem copiar os pesos entre projetos. |

`.env.example` é apenas documentação dessas opções; o programa não carrega um `.env` automaticamente. Não salve senha OBS ali. Para encerrar o servidor, use Ctrl+C no terminal. Não existem recursos cloud criados por esse estúdio para remover; os recursos do laboratório DIO são independentes e não são administrados por ele.

## Verificação

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe audit_release.py
```

Os testes geram mídia sintética temporária identificada como teste; ela não é evidência do pipeline DIO nem acompanha a publicação. Verificam montagem/decodificação, preservação do original, limites de tempo, privacidade HTTP e guarda do controlador OBS com cliente simulado. Consulte [a validação da versão](docs/validacao.md) para resultados executados e limitações, incluindo teste real de síntese local.

## Licenças e créditos

Código próprio sob [MIT](LICENSE). O Qwen3-TTS e seu modelo têm licenças e termos próprios, publicados pelo [projeto Qwen](https://github.com/QwenLM/Qwen3-TTS). A dependência opcional [obsws-python](https://github.com/aatikturk/obsws-python) usa GPL-3.0; as licenças das dependências não são substituídas pela licença deste código. FFmpeg, vozes do Windows e demais pacotes mantêm seus próprios termos. Nenhum peso, binário FFmpeg, amostra de voz ou vídeo do autor foi incluído no Git.
