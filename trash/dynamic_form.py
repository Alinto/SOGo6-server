from app.config.settings.DomainSettings import UserSource
from app.config.settings.FrontWrapperSettings import create_dynamic_dict_for_settings


a = UserSource()
myresult = create_dynamic_dict_for_settings(a)

print("")
print("")

print(myresult)
