# Consulta de preço e promoções

Cenário: conversa real do agente executando via CLI (`python -m emporio_agent --demo examples/demo_messages/02_preco_promocao.txt`).

**Cliente:** Quanto custa o Takamine GD20?

**Assistente:** Oi! O violão Takamine GD20 está disponível por R$ 2.199,00. É um modelo dreadnought com tampo sólido em cedro, ideal para fingerstyle, com timbre quente e definido. Temos 5 unidades em estoque. Deseja mais informações sobre ele?

*Ferramentas consultadas: detalhar_produto*

**Cliente:** Tem alguma promoção ativa na loja?

**Assistente:** Atualmente temos algumas promoções ativas na loja:

- Ohana CK-20 Concert Natural (Ukulele): R$ 549,00 por R$ 439,20 (20% de desconto)
- Crafter HT-100 Folk Aço Natural (Violão): R$ 2.399,00 por R$ 1.967,18 (18% de desconto)
- Kalani KAL-700T Tenor Natural (Ukulele): R$ 359,00 por R$ 323,10 (10% de desconto)
- Taylor 110e Dreadnought Natural (Violão): R$ 5.999,00 por R$ 5.519,08 (8% de desconto)

Deseja saber mais sobre algum desses produtos ou tem outra dúvida?

*Ferramentas consultadas: listar_promocoes*

**Cliente:** Pagando no PIX esse violão fica com desconto também?

**Assistente:** Oi! Sobre o pagamento no PIX, nosso desconto de 5% não é cumulativo com as promoções atuais. Como o Takamine GD20 já está com seu preço normal de R$ 2.199,00, você teria o desconto de 5% se pagasse à vista no PIX, ficando em aproximadamente R$ 2.089,05.

No entanto, se você escolher um dos violões em promoção, como o Crafter HT-100 Folk Aço Natural (R$ 1.967,18), não teria o desconto adicional do PIX, mas já estaria comprando com um valor menor.

Deseja mais informações sobre alguma dessas opções?
