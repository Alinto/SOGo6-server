
#TODO: chercher des données réelles

class MailDetailInterface:
    """
    Interface for fetching detailed information about a mail item.

    This class centralizes the logic to build the JSON response expected by the MailDetail API.
    In the future, it will aggregate data from various sources such as IMAP, databases, or files.
    """
    def __init__(self):
        """
        Initialisation éventuelle (connexion, config, etc)
        """
        pass

    def get_mail_detail(self, account_id: int, folder_id: int, mail_id: int) -> dict | None:
        """
        Retrieve the details of a mail item by its identifier.

        Args:
            mail_id (str): The unique identifier of the mail to fetch.

        Returns:
            dict or None: A dictionary representing the mail in the expected schema format,
                          or None if no mail matches the provided identifier.
        """
        # Pour l’instant, retourne du fake, plus tard va chercher les vraies données
        if mail_id != 0 or folder_id != 0 or account_id != 0:
            return None  # Simule mail non trouvé
        return {
            "attachments": {
                "parts": [
                    {
                        "partId": "1.2",
                        "name": "Capture d’écran du 2025-07-02 14-16-42.png",
                        "contentType": "image/png",
                        "size": 33280,
                        "downloadUri": "/attachments/1.2?dl=True",
                        "displayUri": "http://localhost:3001/attachments/1.1?dl=True"
                    },
                    {
                        "partId": "1.3",
                        "name": "image_name.png",
                        "contentType": "image/png",
                        "size": 110208,
                        "downloadUri": "/attachments/1.3?dl=True",
                        "displayUri": "http://localhost:3001/attachments/1.2?dl=True"
                    }
                ],
                "zipUri": "http://localhost:3001/attachments/1/?dl=True",
                "count": 2
            },
            "id": "1",
            "contentUri": "http://cloud.cleanmail.eu/api/v3/users/tkeriven@alinto.eu/emails/INBOX/fbeb7b20e2b740b3a6f1073d82c04108/882",
            "seen": True,
            "answered": False,
            "recent": False,
            "deleted": False,
            "hasAttachment": False,
            "important": False,
            "date": 1752052527000,
            "subject": "[Alinto] CMA a publié \"Cleanmail 4.16\"",
            "isMailingList": False,
            "from_": "CMA via Alinto <noreply@jamespot.pro>",
            "to": [
                "Henry Fafenback <henry@fafenback.org>",
                "Thibault Keriven <tkeriven@alinto.eu>"
            ],
            "cc": [
                "Sylvain Barré <sbarre@alinto.eu>",
                "Thibault Keriven <tkeriven@alinto.eu>",
                "Arya Stark <astark@alinto.eu>",
                "Thibault Keriven <tkeriven@alinto.eu>",
                "Sylvain Barré 2 <sbarre2@alinto.eu>",
                "Thibault Keriven 2 <tkeriven2@alinto.eu>"
            ],
            "bcc": [],
            "size": 15129,
            "imageBlocked": True,
            "body": "PGRpdiBjbGFzcz0ibWVzc2FnZV9jb250ZW50X3dyYXBwZXIgd3JhcHBlcl80YTdhNTQiPgoNCjxkaXYgbGFuZz0iZnIiIGNsYXNzPSJ0YWdfaHRtbCI+PCEtLSBodG1sIC0tPg0KICAgIA0KICAgICAgICANCiAgICAgICAgDQogICAgICAgIA0KICAgICAgICAgICAgPHN0eWxlPi53cmFwcGVyXzRhN2E1NCAuY29udGVudC1odG1sICoKe21hcmdpbjogMDsNCiAgICAgICAgICAgICAgICBtYXgtd2lkdGg6IDEwMCU7DQogICAgICAgICAgICAgICAgbGluZS1oZWlnaHQ6IDEuNDt9Cjwvc3R5bGU+DQogICAgICAgIA0KICAgICAgICANCiAgICANCiAgICA8ZGl2IHN0eWxlPSJmb250LWZhbWlseTonSGVsdmV0aWNhIE5ldWUnLEhlbHZldGljYSxBcmlhbCxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToxNHB4O21hcmdpbjowO3BhZGRpbmc6MHB4O2JhY2tncm91bmQtY29sb3I6I2VmZWZlZjtjb2xvcjojNTA1MDUwOyIgY2xhc3M9InRhZ19ib2R5Ij48IS0tIGJvZHkgLS0+DQogICAgICAgIA0KICAgICAgICANCiAgICAgICAgDQogICAgICAgIA0KICAgICAgICANCg0KICAgICAgICAgICAgICAgIDx0YWJsZSBjZWxscGFkZGluZz0iMCIgY2VsbHNwYWNpbmc9IjAiIHN0eWxlPSJ3aWR0aDoxMDAlOyI+DQogICAgICAgICAgICA8dHIgc3R5bGU9ImJhY2tncm91bmQ6IzU5NjY3NCI+DQogICAgICAgICAgICAgICAgPHRkPiZuYnNwOzwvdGQ+DQogICAgICAgICAgICAgICAgPHRkIHN0eWxlPSJ3aWR0aDo2MDBweDsiPg0KICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8YSBocmVmPSJodHRwczovL2FsaW50by5qYW1lc3BvdC5wcm8vIiBzdHlsZT0iY29sb3I6I2ZmZjtwYWRkaW5nOjEwcHggMDtmb250LXNpemU6MjdweDt0ZXh0LWRlY29yYXRpb246bm9uZTtmb250LXdlaWdodDpib2xkO2Rpc3BsYXk6YmxvY2s7Ij5BbGludG88L2E+DQogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L3RkPg0KICAgICAgICAgICAgICAgIDx0ZD4mbmJzcDs8L3RkPg0KICAgICAgICAgICAgPC90cj4NCiAgICAgICAgICAgIDx0ciBzdHlsZT0iYmFja2dyb3VuZDojZmZmZmZmOyI+DQogICAgICAgICAgICAgICAgPHRkPiZuYnNwOzwvdGQ+DQogICAgICAgICAgICAgICAgPHRkIHN0eWxlPSJ3aWR0aDo2MDBweDsiPg0KICAgICAgICAgICAgICAgICAgICA8dGFibGUgY2VsbHBhZGRpbmc9IjAiIGNlbGxzcGFjaW5nPSIwIiBzdHlsZT0id2lkdGg6MTAwJTsiPg0KICAgICAgICAgICAgICAgICAgICAgICAgPHRyPg0KICAgICAgICAgICAgICAgICAgICAgICAgICAgIDx0ZCBzdHlsZT0ncGFkZGluZzoyMHB4IDAgMjBweCAwOyc+DQogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIA0KDQo8dGFibGUgc3R5bGU9IndpZHRoOjEwMCU7IiBjZWxscGFkZGluZz0iMCIgY2VsbHNwYWNpbmc9IjAiPg0KDQogICAgPHRyPg0KICAgIDx0ZCBzdHlsZT0icGFkZGluZy1ib3R0b206MjBweDsiPg0KICAgICAgICA8dGFibGUgY2VsbHBhZGRpbmc9IjAiIGNlbGxzcGFjaW5nPSIwIiBzdHlsZT0id2lkdGg6MTAwJTsiPg0KICAgICAgICAgICAgPHRyPg0KICAgICAgICAgICAgICAgIDx0ZCBzdHlsZT0id2lkdGg6NTBweDsiPg0KICAgICAgICAgICAgICAgICAgICA8aW1nIGRhdGEtc3JjPSdodHRwczovL2FsaW50by5qYW1lc3BvdC5wcm8vaW1hZ2VzZWN1cmUvZXlKMGVYQWlPaUpLVjFRaUxDSmhiR2NpT2lKSVV6STFOaUo5LmV5SndZWFJvSWpvaU1UQXdlREV3TUZ3dmRYTmxjbHd2TVRFdWNHNW5QMTg5TVRjek16UTRNakl6TUNKOS4wNmg0UldZcF9sRE5EVUNuamFvMk9SUTNnOWJLUWVncTBoSW5YelVrd2M0JyB3aWR0aD0nNTAnIGhlaWdodD0nNTAnIGNsYXNzPSdpbWFnZWNhY2hlJyB0aXRsZT0iQ01BIiBhbHQ9IiIgc3R5bGU9J2Rpc3BsYXk6YmxvY2s7JyAvPg0KICAgICAgICAgICAgICAgIDwvdGQ+DQogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDx0ZCBzdHlsZT0icGFkZGluZy1sZWZ0OjE1cHg7Zm9udC1zaXplOiAxM3B4OyI+DQogICAgICAgICAgICAgICAgICAgIDxhIGhyZWY9Imh0dHBzOi8vYWxpbnRvLmphbWVzcG90LnByby91c2VyLzExIiBzdHlsZT0iZm9udC13ZWlnaHQ6Ym9sZDtmb250LXNpemU6MThweDtjb2xvcjojNTM1MzUzO3RleHQtZGVjb3JhdGlvbjpub25lOyI+Q01BPC9hPg0KICAgICAgICAgICAgICAgICAgICA8YnI+DQogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGEgcHVibGnDqSB1biBhcnRpY2xlDQogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L3RkPg0KICAgICAgICAgICAgPC90cj4NCiAgICAgICAgPC90YWJsZT4NCiAgICA8L3RkPg0KPC90cj4NCiAgICANCiAgICA8dHI+DQogICAgPHRkIHN0eWxlPSJwYWRkaW5nLWJvdHRvbToxMHB4O2ZvbnQtc2l6ZToxMnB4OyI+DQogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAkJCQk8c3BhbiBzdHlsZT0iY29sb3I6IzcwNzA3MDsiPlZpc2libGUgZGUgOjwvc3Bhbj4NCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIA0KICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8c3BhbiBzdHlsZT0nbGlzdC1zdHlsZTpub25lO3BhZGRpbmc6MDtwYWRkaW5nLWxlZnQ6MTBweDttYXJnaW46MDsnPkdlbmVyYWw8L3NwYW4+DQogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIA0KICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L3RkPg0KPC90cj4NCiAgICAgICAgICAgICAgICA8dHI+DQogICAgPHRkIHN0eWxlPSJiYWNrZ3JvdW5kOiNlZmVmZWY7Ij4NCiAgICAgICAgPHRhYmxlIGNlbGxwYWRkaW5nPSIwIiBjZWxsc3BhY2luZz0iMCI+DQogICAgICAgICAgICA8dHI+DQogICAgICAgICAgICAgICAgPHRkIHN0eWxlPSJ3aWR0aDoxMDBweDtiYWNrZ3JvdW5kOiM1MjliNjA7Ij4NCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8aW1nIGRhdGEtc3JjPSdodHRwczovL2Nkbi5qYW1lc3BvdC5wcm8vcC9hbGludG8uamFtZXNwb3QucHJvL2ltYWdlc3RhdGljLzIwMHgyMDAvaWNvbnMvYXJ0aWNsZS13aGl0ZS5wbmcnIHdpZHRoPScxMDAnIGhlaWdodD0nMTAwJyBjbGFzcz0naW1hZ2VjYWNoZScgYWx0PSIiIHN0eWxlPSdkaXNwbGF5OmJsb2NrOycgLz4NCiAgICAgICAgICAgICAgICA8L3RkPg0KICAgICAgICAgICAgICAgIDx0ZCB2YWxpZ249J3RvcCc+DQogICAgICAgICAgICAgICAgICAgIDxkaXYgc3R5bGU9Im1hcmdpbjoxNXB4IDIwcHg7Ij4NCiAgICAgICAgICAgICAgICAgICAgICAgIDxhIGhyZWY9Imh0dHBzOi8vYWxpbnRvLmphbWVzcG90LnByby9hcnRpY2xlLzM2NjEiIHN0eWxlPSJmb250LXNpemU6MThweDtmb250LXdlaWdodDpib2xkO3RleHQtZGVjb3JhdGlvbjpub25lO2NvbG9yOiM1MjliNjA7Ij5DbGVhbm1haWwgNC4xNjwvYT4gIDxzcGFuIHN0eWxlPSdmb250LXNpemU6MTFweDsnPjA5LzA3LzIwMjU8L3NwYW4+DQogICAgICAgICAgICAgICAgICAgICAgICAJCQkJCQkJPGRpdiBzdHlsZT0ibWFyZ2luLXRvcDoxMHB4OyI+DQoJCQkJCQkJCTxwPkhlbGxvPGJyIC8+DQrCoDxiciAvPg0KUGxlYXNlIHRha2UgYSBsb29rIHRvIG91ciBuZXh0IHJlbGVhc2Ugb2YgQ2xlYW5tYWlsPGJyIC8+DQrCoDxiciAvPg0KPGEgaHJlZj0iaHR0cHM6Ly9kZXZ0b29scy5hbGludG8ub3JnL2FsaW50by9yZXRkL3Byb3RlY3QvcHJvdGVjdC11aS8tL3JlbGVhc2VzLzQuMTYuIj48L2E+Li4uPC9wPg0KDQoJCQkJCQkJPC9kaXY+DQoJCQkJCQkgICAgICAgICAgICAgICAgICAgIDwvZGl2Pg0KICAgICAgICAgICAgICAgIDwvdGQ+DQogICAgICAgICAgICA8L3RyPg0KICAgICAgICA8L3RhYmxlPg0KICAgIDwvdGQ+DQo8L3RyPiAgICANCg0KICAgIA0KDQo8dHI+DQogICAgPHRkIGFsaWduPSJjZW50ZXIiIHN0eWxlPSJwYWRkaW5nLXRvcDozMHB4OyI+DQogICAgICAgICAgICAgICAgPGEgaHJlZj0iaHR0cHM6Ly9hbGludG8uamFtZXNwb3QucHJvL2FydGljbGUvMzY2MSIgc3R5bGU9ImRpc3BsYXk6aW5saW5lLWJsb2NrO2JvcmRlcjoyMHB4IHNvbGlkICM3MzdkOGE7YmFja2dyb3VuZC1jb2xvcjojNzM3ZDhhO2NvbG9yOiNmZmY7dGV4dC1kZWNvcmF0aW9uOm5vbmU7Ij5MaXJlIGxhIHN1aXRlPC9hPg0KICAgIDwvdGQ+DQo8L3RyPiAgICANCjwvdGFibGU+DQogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L3RkPg0KICAgICAgICAgICAgICAgICAgICAgICAgPC90cj4NCiAgICAgICAgICAgICAgICAgICAgPC90YWJsZT4NCiAgICAgICAgICAgICAgICA8L3RkPg0KICAgICAgICAgICAgICAgIDx0ZD4mbmJzcDs8L3RkPg0KICAgICAgICAgICAgPC90cj4NCiAgICAgICAgICAgIDx0cj4NCiAgICAgICAgICAgICAgICA8dGQ+Jm5ic3A7PC90ZD4NCiAgICAgICAgICAgICAgICA8dGQgc3R5bGU9IndpZHRoOjYwMHB4O2ZvbnQtc2l6ZToxMnB4O2NvbG9yOiM3MDcwNzA7cGFkZGluZy10b3A6MTVweDtwYWRkaW5nLWJvdHRvbTozMHB4OyIgdmFsaWduPSJ0b3AiPg0KICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8dGFibGUgY2VsbHBhZGRpbmc9IjAiIGNlbGxzcGFjaW5nPSIwIiBzdHlsZT0nd2lkdGg6MTAwJSc+DQogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICANCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgDQogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDx0cj4NCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDx0ZCBzdHlsZT0idGV4dC1hbGlnbjogY2VudGVyIj4NCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBWb3VzIHJlY2V2ZXogY2UgbWFpbCBwYXJjZSBxdWUgdm91cyDDqnRlcyBtZW1icmUgZGUgbGEgcGxhdGVmb3JtZSA8YSBocmVmPSJodHRwczovL2FsaW50by5qYW1lc3BvdC5wcm8vIiBzdHlsZT0nY29sb3I6IzUzNTM1Mztmb250LXdlaWdodDpib2xkO3RleHQtZGVjb3JhdGlvbjpub25lOycgdGFyZ2V0PSJfYmxhbmsiIHJlbD0ibm9vcGVuZXIgbm9yZWZlcnJlciI+QWxpbnRvPC9hPjxiciAvPkNldCBlbWFpbCBlc3QgZGVzdGluw6kgw6AgVEtFDQogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPGJyLz48YnIvPg0KICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPC90ZD4NCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPC90cj4NCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPHRyPg0KICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPHRkIHN0eWxlPSJ0ZXh0LWFsaWduOiBjZW50ZXIiPg0KICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxhIGhyZWY9Imh0dHBzOi8vYWxpbnRvLmphbWVzcG90LnByby8/YWN0aW9uPXVuc3Vic2NyaWJlTWFpbCZ0b2tlbj1leUowZVhBaU9pSktWMVFpTENKaGJHY2lPaUpJVXpJMU5pSjkuZXlKdFlXbHNJam9pZEd0bGNtbDJaVzVBWVd4cGJuUnZMbVYxSWl3aVpHRjBaU0k2SWpJd01qVXRNRGN0TURraWZRLkFDRGEwUnlWQjlHaFlFc0JJdjZDWkJiT2F6NEUwQXZaQkotbWlQSzhsV00mdGFiPXNsZWVwIj5TZSBkw6lzaW5zY3JpcmU8L2E+DQogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAmbmJzcDstJm5ic3A7DQogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxhIGhyZWY9Imh0dHBzOi8vYWxpbnRvLmphbWVzcG90LnByby8/YWN0aW9uPXVuc3Vic2NyaWJlTWFpbCZ0b2tlbj1leUowZVhBaU9pSktWMVFpTENKaGJHY2lPaUpJVXpJMU5pSjkuZXlKdFlXbHNJam9pZEd0bGNtbDJaVzVBWVd4cGJuUnZMbVYxSWl3aWRYSnBJam9pYlhCQmNuUnBZMnhsWEM4ek5qWXhJaXdpWkdGMFpTSTZJakl3TWpVdE1EY3RNRGtpZlEucXdZdW5MM0Jrcl9RVmlpWno0Q3l4NXdxNHBOWWxueFZmTjJIOEk1R2R4ayZ0YWI9bWFuYWdlIj5Hw6lyZXIgbWVzIG5vdGlmaWNhdGlvbnMgbWFpbDwvYT4NCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPGJyLz48YnIvPg0KICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPC90ZD4NCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPC90cj4NCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPHRyPg0KICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8dGQgc3R5bGU9InRleHQtYWxpZ246IGNlbnRlciI+DQogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBWb3VzIHBvdXZleiBjb250YWN0ZXIgbCdhZG1pbmlzdHJhdGV1ciBkZSBsYSBwbGF0ZWZvcm1lLCBwYXIgPGEgaHJlZj0ibWFpbHRvOm1hcmNvbUBhbGludG8uZXUiIHN0eWxlPSdjb2xvcjojNTM1MzUzO2ZvbnQtd2VpZ2h0OmJvbGQ7dGV4dC1kZWNvcmF0aW9uOm5vbmU7Jz5tYWlsPC9hPjxiciAvPjxiciAvPlByb3B1bHPDqSBwYXIgbGEgc29sdXRpb24gPGEgaHJlZj0iaHR0cHM6Ly93d3cuamFtZXNwb3QuY29tLyIgc3R5bGU9J2NvbG9yOiM1MzUzNTM7Zm9udC13ZWlnaHQ6Ym9sZDt0ZXh0LWRlY29yYXRpb246bm9uZTsnPkphbWVzcG90PC9hPg0KICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPGJyLz48YnIvPg0KICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L3RkPg0KICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvdHI+DQogICAgICAgICAgICAgICAgICAgICAgICA8L3RhYmxlPg0KICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPC90ZD4NCiAgICAgICAgICAgICAgICA8dGQ+Jm5ic3A7PC90ZD4NCiAgICAgICAgICAgIDwvdHI+DQogICAgICAgIDwvdGFibGU+DQogICAgICAgICAgICAgICAgICAgICAgICAgICAgPGltZyBhbHQ9JzF4MScgZGF0YS1zcmM9J2h0dHBzOi8vYWxpbnRvLmphbWVzcG90LnByby9qd3QvZXlKMGVYQWlPaUpLVjFRaUxDSmhiR2NpT2lKSVV6STFOaUo5LmV5SmhZM1JwYjI0aU9pSnRZV2xzZEhKaFkydGxjaUlzSW1sa0lqb2lNVFl3TWlJc0ltbGtWWE5sY2lJNklqUXpJbjAuMnlzTUFITDgyWFUtbmN1enJGZVVVYVBtLTluQ3hXekVlZUh6X1FuMTV0NCcgLz4NCiAgICAgICAgICAgIDwvZGl2PjwhLS0gZW5kIGJvZHkgLS0+DQo8L2Rpdj48IS0tIGVuZCBodG1sIC0tPg0KDQoKPC9kaXY+PCEtLSBlbmQgd3JhcHBlcl80YTdhNTQgLS0+"
        }
