# import random
#import numpy as np
#import matplotlib.pyplot as plt

# f = lambda x,y : x**2 + y

# def potentielle(masse, hauteur):
#     g = 9.81
#     return masse * g * hauteur

# print(f(3,2))
# print(potentielle(3,2))

# L = ["Paris","Londres"]

# L.append("Berlin")

# print(L)

# L.insert(2,"Madrid")

# print(L)

# L2 = ["Rome","Lisbonne"]

# L.extend(L2)

# print(L)

# print(L.count("Paris"))

# print(len(L))

# if "Berlin" in L:
#     print("Berlin est dans la liste")
    
    
# dictionnaire_1 = {"nom":"Dupont", "prenom":"Jean", "age":30}

# print(dictionnaire_1.values())

# print(dictionnaire_1.keys())

# dictionnaire_1["age"] = 31
# print(dictionnaire_1["age"])

# print(dictionnaire_1.get("nom"))

# print(dictionnaire_1.get("taille"))

# print(dictionnaire_1.get("taille", "non renseigné"))

# dictionnaire_2 = {}
# dictionnaire_2.fromkeys(L,"defaut")

# print(dictionnaire_2)

# for k,v in dictionnaire_1.items():
#     print(k,v)
    
    
# classeur = {
#     "positif": [],
#     "negatif": []
# }
    
# def trier(classeur, nombre):
#     if nombre >= 0:
#         classeur["positif"].append(nombre)
#     else:
#         classeur["negatif"].append(nombre)
    
#     return classeur

# for i in range(10):
#     random_number = random.randint(-10, 10)
#     trier(classeur, random_number)
    
# print(classeur)

# liste2 = [random.randint(-10, 10) for i in range(10)]
# print(liste2)

# dico3 = dict({k: k**2 for k in range(0, -20, -1)})

# print(dico3)

# ville="Paris"
# x=20

# message = f"la temprérature de  {ville} est de {x} degrés"
# print(message)

# Vidéo 12 : Exercice

# np.random.seed(0)
# A = np.random.randint(0,100, [10,5]) 
# print(A)

# D = (A - A[:,0].mean()) / A[:,0].std()
    
# print(D)
 
# print(D[:,0].mean())

# dataset = {f"experience{i}": np.random.randn(100) for i in range(4)}
# print(dataset)

# def graphique(dataset):
#     plt.figure()
#     plt.plot(dataset["experience0"], label="experience0")
#     plt.show()

# x = np.linspace(0, 10, 100)
# y = x**2
# plt.figure()
# plt.plot(x,y)
# plt.show()