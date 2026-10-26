# Como este projeto foi usado

O autor executou as etapas do laboratório de dados e construiu um roteiro com base no curso. Para apoiar a apresentação dentro do tempo disponível, usou assistência do Codex para navegar pelas telas, controlar o OBS e preparar uma narração sintética com a própria voz autorizada.

O protótipo original gerou sete cenas narradas, com 31 blocos de fala. A apresentação mostrou telas reais e evidências históricas identificadas. Não foi uma nova execução completa do pipeline: conector Failed, snapshot e alerta histórico foram explicados na narração. Publicar este estúdio não transforma aquelas pendências em provas concluídas.

Esta versão adapta o estúdio para outros projetos: retira caminhos pessoais, não limita a montagem a sete cenas, recebe vídeos do operador e mantém referência, pesos e cache em pasta privada. Os utilitários de montagem e síntese derivam do protótipo; o controlador OBS público é uma implementação portátil reduzida das operações locais utilizadas, com validação por cliente simulado nesta edição.

Não há treinamento de um modelo fundamental próprio. A parte de IA utiliza Qwen3-TTS, com referência de voz local; o restante combina regras de montagem, FFmpeg e API OBS. O roteiro não é escrito automaticamente por este pacote. Não há agente de navegação, acesso a contas, integração Confluent ou extensão de navegador incluída.

Todo usuário deve fornecer os próprios vídeos e uma voz própria ou autorizada. O repositório não distribui a referência vocal do autor, embeddings, gravações pessoais, material original do curso, chaves, cookies, tokens de sessão ou pesos do modelo.
