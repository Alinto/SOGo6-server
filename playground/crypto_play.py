from app.utils.maths.crypto_common import check_password

pwd = "Banane"

pwd_sha256_b64 = "ot8llmsygwSYCM1DfIBqF5A7Cd4N9xmqDj4pbvPvDGY="
pwd_sha256_hex = "{SHA256.HEX}a2df25966b3283049808cd437c806a17903b09de0df719aa0e3e296ef3ef0c66"
pwd_ssha256 = "{SSHA256}Rf491OG1MhvdtqMqhmF/7D+skV+jsBjVv7vJcOQn0YRx+WypH7YWqD6WBO4SsK12"

# print("CRYPT")
# algo = "crypt"
# print(encrypt_password(pwd, algo))

print("sha256")
algo = "sha256"
print(check_password(pwd, pwd_sha256_b64, algo))
print("")
print("sha256.hex")
algo = "sha256.hex"
print(check_password(pwd, pwd_sha256_hex, algo))
print("")
print("ssha256.hex")
algo = "ssha256"
print(check_password(pwd, pwd_ssha256, algo))
print("")


