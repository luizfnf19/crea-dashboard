a = float(input('Quanto custa o produto? R$ '))
b = a * (0.05)
c = a - b
print('O produto que custava R${}, na promoção com 5% de desconto, vai custar R${:.2f}'.format(a, c))
#ou
#b = a (a * 5 / 100)
#print('O produto que custava R${}, na promoção com 5% de desconto, vai custar R${:.2f}'.format(a, b))