from app.utils.maths.crypto_common import encrypt_password


pwd = "Banane"

# print("CRYPT")
# algo = "crypt"
# print(encrypt_password(pwd, algo))

print("md5")
algo = "md5"
print(encrypt_password(pwd, algo))
