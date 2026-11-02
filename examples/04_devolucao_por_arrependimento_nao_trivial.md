# Devolução por arrependimento

Cenário: conversa real do agente executando via CLI (`python -m emporio_agent --demo examples/demo_messages/04_devolucao.txt`).

**Cliente:** Me arrependi da minha compra, posso devolver meu pedido?

**Assistente:** Vamos verificar as informações sobre devolução por arrependimento para você. Por favor, me informe o número do seu pedido ou o telefone cadastrado na loja para que eu possa consultar os detalhes.

**Cliente:** Foi uma compra online, recebi anteontem. É um violão, tá lacrado na caixa, nem abri. Comprei no PIX.

**Assistente:** Ótimo! Como você recebeu o violão anteontem, está perfeitamente dentro do prazo de 7 dias corridos para devolução por arrependimento. 

Como o produto está lacrado e sem uso, e você pagou via PIX, o reembolso será integral na mesma conta em até 10 dias úteis. A loja arca com o custo do frete de devolução.

Para dar andamento ao processo, precisamos do número do seu pedido. Você consegue me informar?

*Ferramentas consultadas: buscar_politicas*

**Cliente:** Como funciona o reembolso então? Quem paga o frete da devolução?

**Assistente:** Com base em nossa política de devoluções, o reembolso será integral na mesma forma de pagamento que você utilizou (PIX), e o valor será creditado de volta na sua conta em até 10 dias úteis.

Quanto ao frete da devolução, a Empório da Música arca com esse custo em caso de arrependimento. Você não precisará pagar nada para devolver o produto.

Para darmos andamento ao processo, ainda preciso do número do seu pedido. Você consegue me fornecer esse número?

*Ferramentas consultadas: buscar_politicas*

**Cliente:** E se depois de aberto eu descobrir um defeito de fabricação, qual o prazo pra trocar e o que a garantia não cobre?

**Assistente:** Se você descobrir um defeito de fabricação após abrir o violão, terá até 30 dias corridos para solicitar a troca. Após esse período, o caminho é acionar a garantia diretamente com o fabricante.

A garantia legal é de 90 dias contra defeitos de fabricação, mas muitos fabricantes oferecem garantias próprias de 6 meses a 2 anos. O certificado de garantia que acompanha seu produto detalha esses prazos específicos.

A garantia não cobre desgaste natural de peças (como trastes ou cordas), danos por mau uso, quedas, exposição a condições extremas ou modificações feitas por terceiros.

Precisa de ajuda com algo relacionado à garantia ou troca do seu violão?

*Ferramentas consultadas: buscar_politicas*
