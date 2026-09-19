"""Profile field metadata: types, enum options, localized labels and questions.

Single source of truth for:
  - the extractor prompt (which fields / values the LLM may output)
  - the normaliser (validation)
  - the planner (question text, button options)
  - display (labels in en/ta/hi)
"""
from __future__ import annotations

LANGS = ("en", "ta", "hi")


def L(en: str, ta: str | None = None, hi: str | None = None) -> dict:
    return {"en": en, "ta": ta or en, "hi": hi or en}


def tr(d: dict | str | None, lang: str) -> str:
    """Pick a language from a localized dict, falling back to English."""
    if d is None:
        return ""
    if isinstance(d, str):
        return d
    return d.get(lang) or d.get("en") or next(iter(d.values()), "")


YES = L("Yes", "ஆம்", "हाँ")
NO = L("No", "இல்லை", "नहीं")
DONT_KNOW = L("Don't know", "தெரியாது", "पता नहीं")

UNORGANISED = [
    "farmer", "agri_labourer", "daily_wage_labourer", "construction_worker",
    "street_vendor", "artisan", "domestic_worker", "fisherman", "self_employed",
]

EDUCATION_ORDER = ["none", "primary", "8th", "10th", "12th", "iti", "diploma", "degree", "postgrad"]

# type: int | float | bool | enum | str | children
# yes/no: phrases used in rule-check texts for bool fields
# buttons: whether the planner may offer quick-reply buttons (enum with few options)
FIELDS: dict[str, dict] = {
    "name": {
        "type": "str", "label": L("Name", "பெயர்", "नाम"),
        "q": L("What is your name?", "உங்கள் பெயர் என்ன?", "आपका नाम क्या है?"),
    },
    "age": {
        "type": "int", "min": 0, "max": 120, "label": L("Age", "வயது", "आयु"),
        "q": L("How old are you?", "உங்கள் வயது என்ன?", "आपकी उम्र क्या है?"),
    },
    "gender": {
        "type": "enum", "label": L("Gender", "பாலினம்", "लिंग"), "buttons": True,
        "options": {
            "female": L("Woman", "பெண்", "महिला"),
            "male": L("Man", "ஆண்", "पुरुष"),
            "transgender": L("Transgender", "திருநங்கை / திருநம்பி", "ट्रांसजेंडर"),
        },
        "q": L("Are you a woman, a man, or transgender?", "நீங்கள் பெண்ணா, ஆணா, அல்லது திருநங்கை/திருநம்பியா?",
               "आप महिला हैं, पुरुष हैं या ट्रांसजेंडर?"),
    },
    "state": {
        "type": "str", "label": L("State", "மாநிலம்", "राज्य"),
        "q": L("Which state do you live in?", "நீங்கள் எந்த மாநிலத்தில் வசிக்கிறீர்கள்?", "आप किस राज्य में रहते हैं?"),
    },
    "district": {
        "type": "str", "label": L("District", "மாவட்டம்", "ज़िला"),
        "q": L("Which district do you live in?", "நீங்கள் எந்த மாவட்டத்தில் வசிக்கிறீர்கள்?", "आप किस ज़िले में रहते हैं?"),
    },
    "residence": {
        "type": "enum", "label": L("Area", "பகுதி", "क्षेत्र"), "buttons": True,
        "options": {
            "rural": L("Village (rural)", "கிராமம்", "गाँव"),
            "urban": L("Town / city (urban)", "நகரம்", "शहर"),
        },
        "q": L("Do you live in a village or in a town/city?", "நீங்கள் கிராமத்தில் வசிக்கிறீர்களா, நகரத்திலா?",
               "आप गाँव में रहते हैं या शहर में?"),
    },
    "marital_status": {
        "type": "enum", "label": L("Marital status", "திருமண நிலை", "वैवाहिक स्थिति"), "buttons": True,
        "options": {
            "single": L("Unmarried", "திருமணமாகாதவர்", "अविवाहित"),
            "married": L("Married", "திருமணமானவர்", "विवाहित"),
            "widowed": L("Widowed", "துணையை இழந்தவர் (விதவை)", "विधवा / विधुर"),
            "divorced": L("Divorced", "விவாகரத்து ஆனவர்", "तलाकशुदा"),
            "separated": L("Separated", "பிரிந்து வாழ்பவர்", "अलग रह रहे"),
        },
        "q": L("What is your marital status?", "உங்கள் திருமண நிலை என்ன?", "आपकी वैवाहिक स्थिति क्या है?"),
    },
    "is_head_of_family": {
        "type": "bool", "label": L("Head of family", "குடும்பத் தலைவர்", "परिवार के मुखिया"),
        "yes": L("Head of the family (on ration card)", "குடும்பத் தலைவர் (ரேஷன் கார்டில்)", "परिवार के मुखिया (राशन कार्ड पर)"),
        "no": L("Not head of the family", "குடும்பத் தலைவர் அல்ல", "परिवार के मुखिया नहीं"),
        "q": L("Are you the head of the family on your ration card?", "ரேஷன் கார்டில் நீங்கள் தான் குடும்பத் தலைவரா?",
               "क्या राशन कार्ड में आप परिवार के मुखिया हैं?"),
    },
    "annual_family_income": {
        "type": "int", "min": 0, "max": 100_000_000,
        "label": L("Annual family income", "குடும்ப ஆண்டு வருமானம்", "परिवार की वार्षिक आय"),
        "q": L("Roughly how much does your whole family earn in a month?",
               "உங்கள் குடும்பத்தின் மொத்த வருமானம் மாதத்துக்கு சுமார் எவ்வளவு?",
               "आपके पूरे परिवार की महीने की कमाई लगभग कितनी है?"),
    },
    "occupation": {
        "type": "enum", "label": L("Work", "வேலை", "काम"), "buttons": True,
        # most common answers as buttons; anything else can still be typed or spoken
        "button_subset": ["agri_labourer", "farmer", "daily_wage_labourer", "construction_worker", "street_vendor",
                          "self_employed", "homemaker", "unemployed", "student"],
        "options": {
            "farmer": L("Farmer", "விவசாயி", "किसान"),
            "agri_labourer": L("Agricultural labourer", "விவசாயக் கூலித் தொழிலாளி", "खेतिहर मज़दूर"),
            "daily_wage_labourer": L("Daily wage labourer", "தினக்கூலித் தொழிலாளி", "दिहाड़ी मज़दूर"),
            "construction_worker": L("Construction worker", "கட்டுமானத் தொழிலாளி", "निर्माण मज़दूर"),
            "street_vendor": L("Street vendor", "தெருவோர வியாபாரி", "रेहड़ी-पटरी विक्रेता"),
            "artisan": L("Artisan / craftsperson", "கைவினைஞர்", "कारीगर"),
            "domestic_worker": L("Domestic worker", "வீட்டு வேலைத் தொழிலாளி", "घरेलू कामगार"),
            "fisherman": L("Fisher", "மீனவர்", "मछुआरा"),
            "self_employed": L("Self-employed", "சுயதொழில்", "स्वरोज़गार"),
            "small_business": L("Small business owner", "சிறு வணிகர்", "छोटा व्यवसायी"),
            "salaried_private": L("Private job", "தனியார் வேலை", "निजी नौकरी"),
            "salaried_govt": L("Government job", "அரசு வேலை", "सरकारी नौकरी"),
            "student": L("Student", "மாணவர்", "छात्र"),
            "unemployed": L("Unemployed", "வேலையில்லை", "बेरोज़गार"),
            "homemaker": L("Homemaker", "இல்லத்தரசி", "गृहिणी"),
            "retired": L("Retired / not working", "ஓய்வு பெற்றவர்", "सेवानिवृत्त"),
            "other": L("Other", "மற்றவை", "अन्य"),
        },
        "q": L("What work do you do?", "நீங்கள் என்ன வேலை செய்கிறீர்கள்?", "आप क्या काम करते हैं?"),
    },
    "caste_category": {
        "type": "enum", "label": L("Community", "சமூகப் பிரிவு", "वर्ग"), "buttons": True,
        "options": {
            "general": L("General", "பொது (OC)", "सामान्य"),
            "obc": L("OBC", "OBC", "OBC"),
            "bc": L("BC", "BC", "BC"),
            "mbc": L("MBC", "MBC", "MBC"),
            "sc": L("SC", "SC", "SC"),
            "st": L("ST", "ST", "ST"),
        },
        "q": L("Which community category do you belong to?", "நீங்கள் எந்த சமூகப் பிரிவைச் சேர்ந்தவர்?",
               "आप किस वर्ग से हैं?"),
    },
    "is_minority": {
        "type": "bool", "label": L("Minority community", "சிறுபான்மையினர்", "अल्पसंख्यक"),
        "yes": L("Minority community", "சிறுபான்மையினர்", "अल्पसंख्यक"),
        "no": L("Not a minority community", "சிறுபான்மையினர் அல்ல", "अल्पसंख्यक नहीं"),
        "q": L("Do you belong to a religious minority community?", "நீங்கள் சிறுபான்மை மதத்தைச் சேர்ந்தவரா?",
               "क्या आप अल्पसंख्यक समुदाय से हैं?"),
    },
    "has_bpl_ration_card": {
        "type": "bool", "label": L("Priority (PHH/AAY) ration card", "முன்னுரிமை (PHH/AAY) ரேஷன் கார்டு", "BPL / प्राथमिकता राशन कार्ड"),
        "yes": L("Has a priority (PHH/AAY/BPL) ration card", "முன்னுரிமை (PHH/AAY) ரேஷன் கார்டு உள்ளது", "BPL / प्राथमिकता राशन कार्ड है"),
        "no": L("No priority ration card", "முன்னுரிமை ரேஷன் கார்டு இல்லை", "BPL राशन कार्ड नहीं"),
        "q": L("Do you have a priority ration card (PHH or AAY / BPL)?",
               "உங்களிடம் முன்னுரிமை ரேஷன் கார்டு (PHH அல்லது AAY) உள்ளதா?",
               "क्या आपके पास BPL / प्राथमिकता (PHH/AAY) राशन कार्ड है?"),
    },
    "owns_agri_land": {
        "type": "bool", "label": L("Owns farm land", "சொந்த விவசாய நிலம்", "अपनी खेती की ज़मीन"),
        "yes": L("Owns agricultural land", "சொந்த விவசாய நிலம் உள்ளது", "अपनी खेती की ज़मीन है"),
        "no": L("No agricultural land of own", "சொந்த விவசாய நிலம் இல்லை", "अपनी खेती की ज़मीन नहीं"),
        "q": L("Do you own any agricultural land?", "உங்களுக்கு சொந்தமாக விவசாய நிலம் உள்ளதா?",
               "क्या आपके पास अपनी खेती की ज़मीन है?"),
    },
    "land_acres": {
        "type": "float", "min": 0, "max": 100000, "label": L("Land (acres)", "நிலம் (ஏக்கர்)", "ज़मीन (एकड़)"),
        "q": L("How many acres of land do you own?", "உங்களுக்கு எத்தனை ஏக்கர் நிலம் உள்ளது?", "आपके पास कितने एकड़ ज़मीन है?"),
    },
    "has_pucca_house": {
        "type": "bool", "label": L("Owns a pucca house", "சொந்த கான்கிரீட் வீடு", "अपना पक्का मकान"),
        "yes": L("Owns a pucca (concrete) house", "சொந்த கான்கிரீட் வீடு உள்ளது", "अपना पक्का मकान है"),
        "no": L("Does not own a pucca house", "சொந்த கான்கிரீட் வீடு இல்லை", "अपना पक्का मकान नहीं"),
        "q": L("Do you own a pucca (concrete) house?", "உங்களுக்கு சொந்தமாக கான்கிரீட் வீடு உள்ளதா?",
               "क्या आपके पास अपना पक्का मकान है?"),
    },
    "owns_house": {
        "type": "bool", "label": L("Owns a house", "சொந்த வீடு", "अपना घर"),
        "yes": L("Owns the house they live in", "சொந்த வீடு உள்ளது", "अपना घर है"),
        "no": L("Does not own a house", "சொந்த வீடு இல்லை", "अपना घर नहीं"),
        "q": L("Do you own the house you live in?", "நீங்கள் வசிக்கும் வீடு சொந்த வீடா?", "क्या आप जिस घर में रहते हैं वह आपका अपना है?"),
    },
    "has_lpg_connection": {
        "type": "bool", "label": L("LPG gas connection", "LPG கேஸ் இணைப்பு", "LPG गैस कनेक्शन"),
        "yes": L("Has an LPG connection", "கேஸ் இணைப்பு உள்ளது", "LPG कनेक्शन है"),
        "no": L("No LPG connection", "கேஸ் இணைப்பு இல்லை", "LPG कनेक्शन नहीं"),
        "q": L("Does your household have an LPG gas connection?", "உங்கள் வீட்டில் LPG கேஸ் இணைப்பு உள்ளதா?",
               "क्या आपके घर में LPG गैस कनेक्शन है?"),
    },
    "has_electricity_connection": {
        "type": "bool", "label": L("Electricity connection", "மின் இணைப்பு", "बिजली कनेक्शन"),
        "yes": L("Has an electricity connection", "மின் இணைப்பு உள்ளது", "बिजली कनेक्शन है"),
        "no": L("No electricity connection", "மின் இணைப்பு இல்லை", "बिजली कनेक्शन नहीं"),
        "q": L("Does your house have an electricity connection?", "உங்கள் வீட்டில் மின் இணைப்பு உள்ளதா?",
               "क्या आपके घर में बिजली कनेक्शन है?"),
    },
    "has_bank_account": {
        "type": "bool", "label": L("Bank account", "வங்கிக் கணக்கு", "बैंक खाता"),
        "yes": L("Has a bank account", "வங்கிக் கணக்கு உள்ளது", "बैंक खाता है"),
        "no": L("No bank account", "வங்கிக் கணக்கு இல்லை", "बैंक खाता नहीं"),
        "q": L("Do you have a bank account?", "உங்களுக்கு வங்கிக் கணக்கு உள்ளதா?", "क्या आपका बैंक खाता है?"),
    },
    "is_income_tax_payer": {
        "type": "bool", "label": L("Income-tax payer", "வருமான வரி செலுத்துபவர்", "आयकरदाता"),
        "yes": L("Pays income tax", "வருமான வரி செலுத்துபவர்", "आयकर भरते हैं"),
        "no": L("Not an income-tax payer", "வருமான வரி செலுத்துபவர் அல்ல", "आयकरदाता नहीं"),
        "q": L("Does anyone in your family pay income tax?", "உங்கள் குடும்பத்தில் யாராவது வருமான வரி செலுத்துகிறார்களா?",
               "क्या आपके परिवार में कोई आयकर भरता है?"),
    },
    "is_govt_employee": {
        "type": "bool", "label": L("Government employee", "அரசு ஊழியர்", "सरकारी कर्मचारी"),
        "yes": L("Government employee", "அரசு ஊழியர்", "सरकारी कर्मचारी"),
        "no": L("Not a government employee", "அரசு ஊழியர் அல்ல", "सरकारी कर्मचारी नहीं"),
        "q": L("Are you a government employee?", "நீங்கள் அரசு ஊழியரா?", "क्या आप सरकारी कर्मचारी हैं?"),
    },
    "is_epfo_member": {
        "type": "bool", "label": L("PF / ESI member", "PF / ESI உறுப்பினர்", "PF / ESI सदस्य"),
        "yes": L("Has PF / ESI at work", "PF / ESI உள்ளது", "PF / ESI कटता है"),
        "no": L("No PF / ESI", "PF / ESI இல்லை", "PF / ESI नहीं"),
        "q": L("Do you get PF or ESI at your work?", "உங்கள் வேலையில் PF அல்லது ESI பிடித்தம் உள்ளதா?",
               "क्या आपके काम पर PF या ESI कटता है?"),
    },
    "has_disability": {
        "type": "bool", "label": L("Disability", "மாற்றுத்திறன்", "दिव्यांगता"),
        "yes": L("Has a disability", "மாற்றுத்திறன் உள்ளது", "दिव्यांगता है"),
        "no": L("No disability", "மாற்றுத்திறன் இல்லை", "कोई दिव्यांगता नहीं"),
        "q": L("Do you have any disability?", "உங்களுக்கு ஏதேனும் மாற்றுத்திறன் (ஊனம்) உள்ளதா?",
               "क्या आपको कोई दिव्यांगता है?"),
    },
    "disability_percent": {
        "type": "int", "min": 0, "max": 100, "label": L("Disability %", "மாற்றுத்திறன் %", "दिव्यांगता %"),
        # planner asks the yes/no question first; "no" sets this to 0
        "ask_first": "has_disability",
        # tap-friendly ranges; representative values sit inside the range, on the correct side of rule thresholds (40/80)
        "choices": [
            {"value": 30, "label": L("Below 40%", "40%க்குக் கீழ்", "40% से कम")},
            {"value": 60, "label": L("40% – 79%", "40% – 79%", "40% – 79%")},
            {"value": 85, "label": L("80% or more", "80% அல்லது அதற்கு மேல்", "80% या अधिक")},
        ],
        "q": L("What disability percentage is on your certificate?",
               "உங்கள் சான்றிதழில் மாற்றுத்திறன் எத்தனை சதவீதம்?",
               "आपके प्रमाणपत्र पर दिव्यांगता कितने प्रतिशत है?"),
    },
    "is_pregnant": {
        "type": "bool", "label": L("Pregnant", "கர்ப்பிணி", "गर्भवती"),
        # only ask when no known fact rules it out (unknown facts don't block)
        "ask_if": [{"field": "gender", "op": "eq", "value": "female"},
                   {"field": "age", "op": "between", "value": [18, 45]},
                   {"field": "marital_status", "op": "in", "value": ["married"]}],
        "yes": L("Pregnant", "கர்ப்பிணி", "गर्भवती"),
        "no": L("Not pregnant", "கர்ப்பிணி அல்ல", "गर्भवती नहीं"),
        "q": L("Are you pregnant at the moment?", "நீங்கள் தற்போது கர்ப்பமாக இருக்கிறீர்களா?", "क्या आप अभी गर्भवती हैं?"),
    },
    "education_level": {
        "type": "enum", "label": L("Education", "கல்வி", "शिक्षा"), "buttons": True,
        "options": {
            "none": L("No schooling", "படிக்கவில்லை", "पढ़ाई नहीं"),
            "primary": L("Primary", "தொடக்கக் கல்வி", "प्राथमिक"),
            "8th": L("8th", "8ஆம் வகுப்பு", "8वीं"),
            "10th": L("10th", "10ஆம் வகுப்பு", "10वीं"),
            "12th": L("12th", "12ஆம் வகுப்பு", "12वीं"),
            "iti": L("ITI", "ITI", "ITI"),
            "diploma": L("Diploma", "டிப்ளமோ", "डिप्लोमा"),
            "degree": L("Degree", "பட்டப்படிப்பு", "स्नातक"),
            "postgrad": L("Post-graduate", "முதுகலை", "स्नातकोत्तर"),
        },
        "q": L("What is your highest education?", "உங்கள் அதிகபட்ச கல்வித் தகுதி என்ன?", "आपकी सबसे ऊँची पढ़ाई क्या है?"),
    },
    "is_student_higher_ed": {
        "ask_if": [{"field": "age", "op": "between", "value": [15, 30]}],
        "type": "bool", "label": L("Studying in college/ITI", "கல்லூரி/ITI மாணவர்", "कॉलेज/ITI में पढ़ाई"),
        "yes": L("Currently in college / ITI / diploma", "தற்போது கல்லூரி / ITI / டிப்ளமோ படிக்கிறார்", "अभी कॉलेज / ITI / डिप्लोमा में"),
        "no": L("Not in higher education", "உயர்கல்வி படிக்கவில்லை", "उच्च शिक्षा में नहीं"),
        "q": L("Are you studying in a college, ITI or diploma course right now?",
               "நீங்கள் தற்போது கல்லூரி, ITI அல்லது டிப்ளமோ படிக்கிறீர்களா?",
               "क्या आप अभी कॉलेज, ITI या डिप्लोमा में पढ़ रहे हैं?"),
    },
    "studied_in_govt_school": {
        "ask_if": [{"field": "age", "op": "between", "value": [15, 30]}],
        "type": "bool", "label": L("Govt school (class 6–12)", "அரசுப் பள்ளி (6–12)", "सरकारी स्कूल (6–12)"),
        "yes": L("Studied class 6–12 in a government school", "6–12 வகுப்பு அரசுப் பள்ளியில் படித்தவர்", "कक्षा 6–12 सरकारी स्कूल में पढ़े"),
        "no": L("Did not study in a government school", "அரசுப் பள்ளியில் படிக்கவில்லை", "सरकारी स्कूल में नहीं पढ़े"),
        "q": L("Did you study from class 6 to 12 in a government school?",
               "நீங்கள் 6 முதல் 12ஆம் வகுப்பு வரை அரசுப் பள்ளியில் படித்தீர்களா?",
               "क्या आपने कक्षा 6 से 12 तक सरकारी स्कूल में पढ़ाई की?"),
    },
    "wants_to_start_business": {
        "type": "bool", "label": L("Wants to start a business", "தொழில் தொடங்க விருப்பம்", "व्यवसाय शुरू करना चाहते हैं"),
        "yes": L("Wants to start or grow a business", "தொழில் தொடங்க / விரிவாக்க விரும்புகிறார்", "व्यवसाय शुरू करना / बढ़ाना चाहते हैं"),
        "no": L("Not planning a business", "தொழில் தொடங்கும் திட்டம் இல்லை", "व्यवसाय की योजना नहीं"),
        "q": L("Do you want to start or grow your own business?", "நீங்கள் சொந்தத் தொழில் தொடங்க அல்லது விரிவாக்க விரும்புகிறீர்களா?",
               "क्या आप अपना व्यवसाय शुरू करना या बढ़ाना चाहते हैं?"),
    },
    "is_first_gen_entrepreneur": {
        "type": "bool", "label": L("First-generation entrepreneur", "முதல் தலைமுறை தொழில்முனைவோர்", "पहली पीढ़ी के उद्यमी"),
        "yes": L("First-generation entrepreneur", "முதல் தலைமுறை தொழில்முனைவோர்", "पहली पीढ़ी के उद्यमी"),
        "no": L("Not first-generation entrepreneur", "முதல் தலைமுறை தொழில்முனைவோர் அல்ல", "पहली पीढ़ी के उद्यमी नहीं"),
        "q": L("Would you be the first person in your family to run a business?",
               "உங்கள் குடும்பத்தில் தொழில் நடத்தும் முதல் நபர் நீங்களா?",
               "क्या आप अपने परिवार में व्यवसाय चलाने वाले पहले व्यक्ति होंगे?"),
    },
    "children": {
        "type": "children", "label": L("Children", "குழந்தைகள்", "बच्चे"),
        "q": L("Do you have children? Please tell me their ages and whether each is a boy or a girl.",
               "உங்களுக்குக் குழந்தைகள் உள்ளனரா? அவர்களின் வயதையும், ஆணா பெண்ணா என்பதையும் சொல்லுங்கள்.",
               "क्या आपके बच्चे हैं? उनकी उम्र और लड़का है या लड़की, बताइए।"),
    },
}

# Derived fields: labels for rule-check texts + which input field the planner should ask about.
DERIVED: dict[str, dict] = {
    "has_girl_child_under_10": {
        "source": "children",
        "yes": L("Has a daughter under 10", "10 வயதுக்குட்பட்ட மகள் உள்ளார்", "10 साल से कम उम्र की बेटी है"),
        "no": L("No daughter under 10", "10 வயதுக்குட்பட்ட மகள் இல்லை", "10 साल से कम उम्र की बेटी नहीं"),
    },
    "has_girl_child_in_govt_school_14_17": {
        "source": "children",
        "yes": L("Daughter (14–17) in a government school", "அரசுப் பள்ளியில் படிக்கும் 14–17 வயது மகள்", "सरकारी स्कूल में 14–17 साल की बेटी"),
        "no": L("No daughter (14–17) in a government school", "அரசுப் பள்ளியில் 14–17 வயது மகள் இல்லை", "सरकारी स्कूल में 14–17 साल की बेटी नहीं"),
    },
    "has_boy_child_in_govt_school_14_17": {
        "source": "children",
        "yes": L("Son (14–17) in a government school", "அரசுப் பள்ளியில் படிக்கும் 14–17 வயது மகன்", "सरकारी स्कूल में 14–17 साल का बेटा"),
        "no": L("No son (14–17) in a government school", "அரசுப் பள்ளியில் 14–17 வயது மகன் இல்லை", "सरकारी स्कूल में 14–17 साल का बेटा नहीं"),
    },
    "caste_is_sc_st": {
        "source": "caste_category",
        "yes": L("SC / ST community", "SC / ST சமூகம்", "SC / ST वर्ग"),
        "no": L("Not SC / ST", "SC / ST அல்ல", "SC / ST नहीं"),
    },
}

# Fields that can be inferred; if still unknown the planner asks the field itself.
INFERRED_FROM = {"is_govt_employee": "occupation", "is_income_tax_payer": "annual_family_income"}

FIELD_PRIORITY = [
    "age", "gender", "state", "annual_family_income", "occupation", "marital_status", "residence",
    "has_bpl_ration_card", "children", "is_head_of_family", "caste_category", "has_pucca_house",
    "has_lpg_connection", "owns_agri_land", "education_level", "is_pregnant", "has_disability", "disability_percent",
    "wants_to_start_business", "is_student_higher_ed", "studied_in_govt_school", "is_first_gen_entrepreneur",
    "is_govt_employee", "is_income_tax_payer", "is_epfo_member", "owns_house", "has_electricity_connection",
    "has_bank_account", "is_minority", "district", "land_acres",
]

DOC_LABELS: dict[str, dict] = {
    "aadhaar": L("Aadhaar card", "ஆதார் அட்டை", "आधार कार्ड"),
    "ration_card": L("Ration card", "ரேஷன் கார்டு", "राशन कार्ड"),
    "income_certificate": L("Income certificate", "வருமானச் சான்றிதழ்", "आय प्रमाण पत्र"),
    "community_certificate": L("Community (caste) certificate", "சாதிச் சான்றிதழ்", "जाति प्रमाण पत्र"),
    "age_proof": L("Age proof", "வயதுச் சான்று", "आयु प्रमाण"),
    "bank_passbook": L("Bank passbook", "வங்கிப் புத்தகம்", "बैंक पासबुक"),
    "land_records": L("Land records (patta / chitta)", "நில ஆவணங்கள் (பட்டா / சிட்டா)", "भूमि रिकॉर्ड"),
    "death_certificate_spouse": L("Spouse's death certificate", "கணவர் / மனைவி இறப்புச் சான்றிதழ்", "पति/पत्नी का मृत्यु प्रमाण पत्र"),
    "disability_certificate": L("Disability certificate (UDID)", "மாற்றுத்திறனாளி சான்றிதழ் (UDID)", "दिव्यांगता प्रमाण पत्र (UDID)"),
    "school_certificate": L("School certificate (TC / bonafide)", "பள்ளிச் சான்றிதழ் (TC)", "स्कूल प्रमाण पत्र (TC)"),
    "college_admission_proof": L("College admission proof", "கல்லூரிச் சேர்க்கைச் சான்று", "कॉलेज प्रवेश प्रमाण"),
    "pregnancy_registration": L("Pregnancy registration (PICME number)", "கர்ப்பப் பதிவு (PICME எண்)", "गर्भावस्था पंजीकरण"),
    "birth_certificate_child": L("Child's birth certificate", "குழந்தையின் பிறப்புச் சான்றிதழ்", "बच्चे का जन्म प्रमाण पत्र"),
    "photo": L("Passport-size photo", "பாஸ்போர்ட் அளவு புகைப்படம்", "पासपोर्ट साइज़ फोटो"),
    "residence_proof": L("Residence proof", "இருப்பிடச் சான்று", "निवास प्रमाण"),
    "project_report": L("Business project report", "தொழில் திட்ட அறிக்கை", "व्यवसाय परियोजना रिपोर्ट"),
    "educational_certificate": L("Educational certificates", "கல்விச் சான்றிதழ்கள்", "शैक्षणिक प्रमाण पत्र"),
    "electricity_bill": L("Electricity bill", "மின் கட்டண ரசீது", "बिजली बिल"),
    "vending_certificate": L("Vending certificate / ULB letter", "வியாபாரச் சான்று / நகராட்சி கடிதம்", "वेंडिंग प्रमाण पत्र"),
}

TN_DISTRICTS = {
    "ariyalur", "chengalpattu", "chennai", "coimbatore", "cuddalore", "dharmapuri", "dindigul", "erode",
    "kallakurichi", "kanchipuram", "kancheepuram", "kanyakumari", "karur", "krishnagiri", "madurai",
    "mayiladuthurai", "nagapattinam", "namakkal", "nilgiris", "the nilgiris", "perambalur", "pudukkottai",
    "ramanathapuram", "ranipet", "salem", "sivaganga", "tenkasi", "thanjavur", "theni", "thoothukudi",
    "tuticorin", "tiruchirappalli", "trichy", "tirunelveli", "tirupathur", "tiruppur", "tiruvallur",
    "tiruvannamalai", "tiruvarur", "vellore", "viluppuram", "villupuram", "virudhunagar",
}

STATE_CODES = {
    "tamil nadu": "TN", "tamilnadu": "TN", "tn": "TN", "kerala": "KL", "karnataka": "KA",
    "andhra pradesh": "AP", "telangana": "TG", "puducherry": "PY", "pondicherry": "PY",
    "maharashtra": "MH", "delhi": "DL", "uttar pradesh": "UP", "bihar": "BR", "west bengal": "WB",
    "gujarat": "GJ", "rajasthan": "RJ", "madhya pradesh": "MP", "odisha": "OD", "punjab": "PB",
    # remaining states and union territories, so schemes from anywhere in India can be catalogued
    "arunachal pradesh": "AR", "assam": "AS", "chhattisgarh": "CG", "goa": "GA", "haryana": "HR",
    "himachal pradesh": "HP", "jharkhand": "JH", "manipur": "MN", "meghalaya": "ML", "mizoram": "MZ",
    "nagaland": "NL", "sikkim": "SK", "tripura": "TR", "uttarakhand": "UK",
    "andaman and nicobar islands": "AN", "chandigarh": "CH", "dadra and nagar haveli and daman and diu": "DH",
    "jammu and kashmir": "JK", "ladakh": "LA", "lakshadweep": "LD", "new delhi": "DL",
}
STATE_NAMES = {"TN": L("Tamil Nadu", "தமிழ்நாடு", "तमिलनाडु")}
# Residence rule text for state schemes; add a state here when its schemes are added to the catalogue.
RESIDENT_OF = {"TN": L("Lives in Tamil Nadu", "தமிழ்நாட்டில் வசிப்பவர்", "तमिलनाडु में निवास")}


def lives_in(state: str) -> dict:
    return RESIDENT_OF.get(state) or L(f"Lives in {state}")

UI = {
    "you": L("you", "நீங்கள்", "आप"),
    "per_year": L("/year", "/ஆண்டு", "/वर्ष"),
    "daughter": L("Daughter", "மகள்", "बेटी"),
    "son": L("Son", "மகன்", "बेटा"),
    "child": L("Child", "குழந்தை", "बच्चा"),
    "no_children": L("No children", "குழந்தைகள் இல்லை", "कोई बच्चा नहीं"),
    "one_of": L("At least one of", "இவற்றில் ஏதேனும் ஒன்று", "इनमें से कोई एक"),
    "disclaimer": L(
        "This is indicative only, based on what you shared. Final eligibility is decided by the concerned government department.",
        "இது நீங்கள் கொடுத்த தகவலின் அடிப்படையிலான தோராயமான முடிவு மட்டுமே. இறுதித் தகுதியை சம்பந்தப்பட்ட அரசுத் துறை தீர்மானிக்கும்.",
        "यह आपकी दी गई जानकारी पर आधारित केवल एक अनुमान है। अंतिम पात्रता संबंधित सरकारी विभाग तय करेगा।",
    ),
    "opening": L(
        "To find schemes for you, tell me a little about yourself: your age, your village/town and district, what work you do, and roughly how much your family earns in a month.",
        "உங்களுக்கான திட்டங்களைக் கண்டறிய, உங்களைப் பற்றி கொஞ்சம் சொல்லுங்கள்: உங்கள் வயது, ஊர் மற்றும் மாவட்டம், நீங்கள் செய்யும் வேலை, குடும்பத்தின் மாத வருமானம்.",
        "आपके लिए योजनाएँ खोजने के लिए अपने बारे में थोड़ा बताइए: आपकी उम्र, गाँव/शहर और ज़िला, आप क्या काम करते हैं, और परिवार की महीने की कमाई लगभग कितनी है।",
    ),
    "future_pudhumai": L(
        "When your daughter joins college after studying in a government school, she can get ₹1,000/month under Pudhumai Penn.",
        "அரசுப் பள்ளியில் படித்த உங்கள் மகள் கல்லூரியில் சேரும்போது, புதுமைப் பெண் திட்டத்தின் கீழ் மாதம் ₹1,000 பெறலாம்.",
        "सरकारी स्कूल में पढ़ी आपकी बेटी कॉलेज जाने पर पुदुमई पेण्ण योजना में ₹1,000/माह पा सकती है।",
    ),
    "future_pudhalvan": L(
        "When your son joins college after studying in a government school, he can get ₹1,000/month under Tamil Pudhalvan.",
        "அரசுப் பள்ளியில் படித்த உங்கள் மகன் கல்லூரியில் சேரும்போது, தமிழ்ப் புதல்வன் திட்டத்தின் கீழ் மாதம் ₹1,000 பெறலாம்.",
        "सरकारी स्कूल में पढ़ा आपका बेटा कॉलेज जाने पर तमिल पुदल्वन योजना में ₹1,000/माह पा सकता है।",
    ),
    "future_ssy": L(
        "You can open a Sukanya Samriddhi account for your daughter before she turns 10.",
        "உங்கள் மகளுக்கு 10 வயதாகும் முன் செல்வமகள் சேமிப்புக் கணக்கு (சுகன்யா சம்ரித்தி) தொடங்கலாம்.",
        "बेटी के 10 साल की होने से पहले सुकन्या समृद्धि खाता खोल सकते हैं।",
    ),
}
