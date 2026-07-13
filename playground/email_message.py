import email
from email.header import decode_header, make_header
from email.utils import parseaddr, getaddresses

mail_bytes = b'Return-Path: <sogo-tests2@example.org>\r\nX-Priority: 2 (High)\r\nDelivered-To: sogo-tests1@example.org\r\nReceived:from localhost ([172.18.0.7])\r\n\tby ac49f475e77f with LMTP\r\n\tid uGMyEfGah2jPAQAA4bfimA\r\n\t(envelope-from <sogo-tests2@example.org>)\r\n\tfor <sogo-tests1@example.org>; Mon, 28 Jul 2025 15:44:49 +0000\r\nReceived: from 9bc80f8b1112 (sogo.sogo-devenv_default [172.18.0.8])\r\n\tby localhost (Postfix) with ESMTP id 37241164A5A\r\n\tfor <sogo-tests1@example.org>; Mon, 28 Jul 2025 15:44:49 +0000 (UTC)\r\nFrom: "Hewill" <sogo-tests2@example.org>\r\nContent-Type: multipart/mixed; boundary="----=_=-_OpenGroupware_org_NGMime-139456-1753717489.131786-0------"\r\nMIME-Version: 1.0\r\nDate: Mon, 28 Jul 2025 17:44:49 +0200\r\nSubject: Invitation =?utf-8?q?accept=C3=A9e?==?utf-8?q?_=3A?=\r\n =?utf-8?q?_=C2=ABtest=C2=BB?=\r\nMessage-ID: <ad7d77eb-d21b-0606-6e90-018077babfba@example.org>\r\nX-Sogo-Message-Type: calendar:invitation-reply\r\nTo: "BGBG 23" <sogo-tests1@example.org>\r\n\r\n------=_=-_OpenGroupware_org_NGMime-139456-1753717489.131786-0------\r\nContent-Type: text/html; charset=utf-8\r\nContent-Transfer-Encoding: quoted-printable\r\nContent-Length: 705\r\n\r\n<html>\r\n\r\n  <head>\r\n    <style type=3D"text/css">\r\nth, td { font-family: Lucida Grande, Bitstream VeraSans, Tahoma, sans-s=\r\nerif; font-size: 12px; line-height: 18px; }\r\nth { font-weight: bold; white-space: nowrap; vertical-align: top; }\r\n    </style>\r\n  </head>\r\n  <body>\r\n    <table style=3D"width: 100%; max-width: 600px;" border=3D"0" cellsp=\r\nacing=3D"2" cellpadding=3D"2">\r\n      <tr>\r\n      <th />\r\n      <td><h1 style=3D"font-size: 18px; font-weight: normal; padding-bo=\r\nttom: 9px; border-bottom: 1px solid #ccc;">Invitation accept=C3=A9e : =C2=\r\n=ABtest=C2=BB</h1></td>\r\n      </tr>\r\n      <tr>\r\n        <th />\r\n        <td>Hewill a accept=C3=A9 votre invitation.</td>\r\n      </tr>\r\n    </table>\r\n  </body>\r\n</html>\r\n\r\n------=_=-_OpenGroupware_org_NGMime-139456-1753717489.131786-0------\r\nContent-Type: text/calendar; method=REPLY; charset="UTF-8"\r\nContent-Class: urn:content-classes:calendarmessage\r\nContent-Transfer-Encoding: quoted-printable\r\nContent-Length: 944\r\n\r\nBEGIN:VCALENDAR\r\nPRODID:-//Inverse inc./SOGo 5.12.3//EN\r\nVERSION:2.0\r\nMETHOD:REPLY\r\nBEGIN:VTIMEZONE\r\nTZID:Europe/Paris\r\nLAST-MODIFIED:20250324T091428Z\r\nX-LIC-LOCATION:Europe/Paris\r\nBEGIN:DAYLIGHT\r\nTZNAME:CEST\r\nTZOFFSETFROM:+0100\r\nTZOFFSETTO:+0200\r\nDTSTART:19700329T020000\r\nRRULE:FREQ=3DYEARLY;BYMONTH=3D3;BYDAY=3D-1SU\r\nEND:DAYLIGHT\r\nBEGIN:STANDARD\r\nTZNAME:CET\r\nTZOFFSETFROM:+0200\r\nTZOFFSETTO:+0100\r\nDTSTART:19701025T030000\r\nRRULE:FREQ=3DYEARLY;BYMONTH=3D10;BYDAY=3D-1SU\r\nEND:STANDARD\r\nEND:VTIMEZONE\r\nBEGIN:VEVENT\r\nUID:220BE-68879A80-1-206F9F00\r\nSUMMARY:test\r\nCLASS:PUBLIC\r\nTRANSP:OPAQUE\r\nDTSTART;TZID=3DEurope/Paris:20250729T110000\r\nDTEND;TZID=3DEurope/Paris:20250729T120000\r\nORGANIZER;CN=3DBGBG 23:mailto:sogo-tests1@example.org\r\nCREATED:20250728T154311Z\r\nDTSTAMP:20250728T154311Z\r\nLAST-MODIFIED:20250728T154311Z\r\nATTENDEE;ROLE=3DREQ-PARTICIPANT;PARTSTAT=3DACCEPTED;CN=3DHewill:mailto:=\r\nsogo-tests\r\n 2@example.org\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n\r\n\r\n------=_=-_OpenGroupware_org_NGMime-139456-1753717489.131786-0--------\r\n\r\n'

mail = email.message_from_bytes(mail_bytes)

# a = mail.get("Subject", "")
# print(a)
# b = decode_header(a)
# print(b)
# c = make_header(b)
# print(c)

# print("")

# a1 = mail.get("From", "")
# print(a1)
# b1 = parseaddr(a1)
# print(b1)

# print("")

# a3 = mail.get("X-Priority", "")
# print(a3)
# b3 = decode_header(a3)
# print(b3)
# c3 = make_header(b3)
# print(c3)

for part in mail.walk():
    print(part)
    print("------------------------------------------------------")
