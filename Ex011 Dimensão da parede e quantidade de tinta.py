a = float(input('Largura da Parede: '))
b = float(input('Altura da parede: '))
c = a*b
d = c/2
print('Sua parede tem a dimensão de {}x{} e sua área é de {:.2f}m2'.format(a, b, c))
print('Para pintar sua parede, você precisará de {:.2f}l de tinta'.format(d))
