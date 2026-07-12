name = "stas"
current_year = 2026
birth_year = 2009
name_cat ="Anna"
cats = ["andru","sebastian","ulia"]

age = current_year - birth_year

print("hello, I am " + name)
print("my " )
print (age)
print ("I love " + name_cat)

def check_user():
    if age>= 18:
     print ("yes 18+ ")
    else:
     print("No 18 dont")


print(cats[0]) 
print(cats[2]) 

for cat in cats:
    print ("hello, baby " + cat)

def say_hello(): # pusk 1 klavesnice i kod funguje
    print("Hello od funkce")
    print("vono funguje")

check_user()
say_hello()
