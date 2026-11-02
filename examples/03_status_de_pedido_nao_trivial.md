# Status de pedido e rastreamento

Cenário: conversa real do agente executando via CLI (`python -m emporio_agent --demo examples/demo_messages/03_status_pedido.txt`).

**Cliente:** Boa tarde! Eu fiz uma compra semana passada e ainda não recebi nada, cadê meu pedido?

**Assistente:** Oi! Tudo bem? 

Para te ajudar a localizar seu pedido, preciso verificar as informações no nosso sistema. Por favor, você consegue me informar o número do pedido ou o telefone que usou na compra? Assim eu consigo dar uma olhada no status pra você.

**Cliente:** Meu telefone é (67) 99654-7821

**Assistente:** Consegui localizar seu pedido! Ana, seu pedido de nº 8 com o violão Kala KA-C Concert Mogno já foi enviado e está em trânsito. O código de rastreio é BRJL5544332BR e a entrega está prevista para 28/02/2026.

Você pode acompanhar a entrega pelo site dos Correios usando esse código. Alguma dúvida sobre o envio?

*Ferramentas consultadas: consultar_pedido*

**Cliente:** E como eu uso esse código de rastreio?

**Assistente:** É bem simples, Ana! Basta acessar o site dos Correios (www.correios.com.br) e procurar por "Rastreamento de Encomendas". Lá você coloca o código BRJL5544332BR e verá a localização atual da sua entrega e o histórico do trajeto.

Além disso, geralmente você recebe notificações por SMS ou e-mail a cada atualização da entrega. Alguma outra dúvida sobre seu pedido?

**Cliente:** Quanto tempo de garantia o produto comprado tem?

**Assistente:** O violão Kala KA-C Concert Mogno que você comprou tem garantia legal de 90 dias contra defeitos de fabricação, conforme o Código de Defesa do Consumidor. Além disso, o fabricante oferece garantia própria que pode variar de 6 meses a 2 anos - os prazos específicos estão detalhados no certificado de garantia que acompanha o produto.

Caso encontre algum defeito, você pode trocar o instrumento em até 30 dias corridos após a compra. Após esse prazo, precisará acionar diretamente o fabricante, mas podemos intermediar o processo se precisar de ajuda.

Lembrando que a garantia não cobre desgaste natural de peças, danos por mau uso, quedas ou modificações não autorizadas.

Tem alguma outra dúvida sobre a garantia do seu violão?

*Ferramentas consultadas: buscar_politicas*
