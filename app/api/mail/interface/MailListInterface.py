
#TODO: chercher des données réelles

class MailListInterface:
    """
    Interface for fetching the list of mails in a folder.

    This class centralizes the logic to build the JSON response expected by the MailList API.
    In the future, it can aggregate data from different sources (IMAP, database, etc.).
    """
    def get_mail_list(self, account_id: int, folder_id: int) -> list[dict] | None:
        """
        Retrieve the list of mails in a given folder.

        Args:
            folder_id (int): The ID of the folder to fetch the mail list from.

        Returns:
            list or None: A list of mail dicts, or None if the folder does not exist.
        """
        # Simulation: always returns the same list for example
        if folder_id != 0 or account_id != 0:
            return None
        return [
            {
                "id": "1",
                "subject": "Welcome to SOGo!",
                "from": {"name": "SOGo Team", "email": "team@sogo.org"},
                "to": [{"name": "User", "email": "user@example.com"}],
                "date": "2025-05-27T12:30:00Z",
                "seen": False,
                "flagged": False,
                "hasAttachment": False,
                "snippet": "Thank you for trying SOGo. Here are some tips to get started..."
            },
            {
                "id": "2",
                "subject": "Your Invoice for May",
                "from": {"name": "Billing", "email": "billing@example.com"},
                "to": [{"name": "User", "email": "user@example.com"}],
                "date": "2024-05-26T15:30:00Z",
                "seen": True,
                "flagged": False,
                "hasAttachment": True,
                "snippet": "Please find attached your invoice for May 2024."
            },
            {
                "id": "3",
                "subject": "Hi friend!",
                "from": {"name": "Paul Luap", "email": "pluap@example.com"},
                "to": [{"name": "User", "email": "user@example.com"}],
                "date": "2024-05-26T15:15:00Z",
                "seen": True,
                "flagged": False,
                "hasAttachment": True,
                "snippet": "Just wanted to say hello!"
            }
        ]
    