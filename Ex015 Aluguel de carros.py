a = (int(input('Quantos dias alugados? ')))
b = (float(input('Quantos km rodados? ')))
c = (a*60) + (b*0.15)
print('O total a pagar é de R${:.2f}.'.format(c))
