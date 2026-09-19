"""
Bot UI strings (en / ta / hi).
Scheme and field text comes localized from the server.
"""
from __future__ import annotations

S: dict[str, dict[str, str]] = {
    "welcome": {
        "en": "🙏 <b>Vanakkam! I'm Urimai (உரிமை).</b>\nI help you find government welfare schemes you may be eligible for — just by chatting or sending a voice note.\n\nChoose your language / மொழியைத் தேர்ந்தெடுக்கவும் / भाषा चुनें:",
    },
    "intro": {
        "en": "Great! Tell me about yourself — type, or send a 🎙️ voice note.\n\nFor example: your age, your village/town and district, what work you do, and roughly how much your family earns in a month.\n\n🔒 I never ask for Aadhaar, phone or bank numbers. Nothing is kept after the chat.",
        "ta": "சரி! உங்களைப் பற்றிச் சொல்லுங்கள் — தட்டச்சு செய்யலாம் அல்லது 🎙️ குரல் செய்தி அனுப்பலாம்.\n\nஉதாரணமாக: உங்கள் வயது, ஊர் மற்றும் மாவட்டம், நீங்கள் செய்யும் வேலை, குடும்பத்தின் மாத வருமானம்.\n\n🔒 ஆதார், தொலைபேசி, வங்கி எண்களை நான் ஒருபோதும் கேட்பதில்லை. உரையாடலுக்குப் பிறகு எதுவும் சேமிக்கப்படாது.",
        "hi": "ठीक है! अपने बारे में बताइए — टाइप करें या 🎙️ वॉइस नोट भेजें।\n\nजैसे: आपकी उम्र, गाँव/शहर और ज़िला, आप क्या काम करते हैं, और परिवार की महीने की कमाई लगभग कितनी है।\n\n🔒 मैं कभी आधार, फ़ोन या बैंक नंबर नहीं माँगता। बातचीत के बाद कुछ भी नहीं रखा जाता।",
    },
    "disclaimer": {
        "en": "Indicative only. Final eligibility is decided by the concerned government department.",
        "ta": "இது தோராயமான தகவல் மட்டுமே. இறுதித் தகுதியை சம்பந்தப்பட்ட அரசுத் துறை தீர்மானிக்கும்.",
        "hi": "यह केवल अनुमान है। अंतिम पात्रता संबंधित सरकारी विभाग तय करेगा।",
    },
    "heard": {"en": "🎙️ I heard:", "ta": "🎙️ கேட்டது:", "hi": "🎙️ सुना:"},
    "understood": {"en": "📋 Got it:", "ta": "📋 புரிந்தது:", "hi": "📋 समझा:"},
    "corrected": {"en": "✏️ Updated:", "ta": "✏️ திருத்தம்:", "hi": "✏️ बदला:"},
    "card_title": {"en": "🎯 Schemes for you", "ta": "🎯 உங்களுக்கான திட்டங்கள்", "hi": "🎯 आपके लिए योजनाएँ"},
    "likely": {"en": "Likely", "ta": "வாய்ப்புள்ளவை", "hi": "संभावित"},
    "need_info": {"en": "Need info", "ta": "தகவல் தேவை", "hi": "जानकारी चाहिए"},
    "not_eligible": {"en": "Not eligible", "ta": "தகுதியில்லை", "hi": "पात्र नहीं"},
    "per_year": {"en": "a year", "ta": "ஆண்டுக்கு", "hi": "प्रति वर्ष"},
    "no_results": {
        "en": "No likely schemes yet — tell me a bit more about yourself.",
        "ta": "இன்னும் திட்டங்கள் கண்டறியப்படவில்லை — உங்களைப் பற்றி இன்னும் கொஞ்சம் சொல்லுங்கள்.",
        "hi": "अभी कोई संभावित योजना नहीं — अपने बारे में थोड़ा और बताइए।",
    },
    "btn_docs": {"en": "📄 Documents", "ta": "📄 ஆவணங்கள்", "hi": "📄 दस्तावेज़"},
    "btn_back": {"en": "◀ Back", "ta": "◀ பின்செல்", "hi": "◀ वापस"},
    "btn_retry": {"en": "🔁 Retry", "ta": "🔁 மீண்டும் முயற்சி", "hi": "🔁 फिर से"},
    "docs_title": {"en": "📄 Documents to keep ready", "ta": "📄 தயார் செய்ய வேண்டிய ஆவணங்கள்", "hi": "📄 तैयार रखने वाले दस्तावेज़"},
    "needed_for": {"en": "for {n} schemes", "ta": "{n} திட்டங்களுக்கு", "hi": "{n} योजनाओं के लिए"},
    "needed_for_one": {"en": "for 1 scheme", "ta": "1 திட்டத்துக்கு", "hi": "1 योजना के लिए"},
    "no_docs": {"en": "No documents yet — first let's find your schemes.", "ta": "இன்னும் ஆவணங்கள் இல்லை — முதலில் திட்டங்களைக் கண்டறிவோம்.", "hi": "अभी कोई दस्तावेज़ नहीं — पहले योजनाएँ ढूँढते हैं।"},
    "status_likely": {"en": "looks likely", "ta": "வாய்ப்புள்ளது", "hi": "संभावित"},
    "status_need_info": {"en": "need more info", "ta": "மேலும் தகவல் தேவை", "hi": "और जानकारी चाहिए"},
    "status_not_eligible": {"en": "not eligible", "ta": "தகுதியில்லை", "hi": "पात्र नहीं"},
    "why": {"en": "Why", "ta": "ஏன்", "hi": "क्यों"},
    "reason": {"en": "Reason", "ta": "காரணம்", "hi": "कारण"},
    "tell_me": {"en": "Still need", "ta": "இன்னும் தேவை", "hi": "और चाहिए"},
    "documents": {"en": "Documents", "ta": "ஆவணங்கள்", "hi": "दस्तावेज़"},
    "how": {"en": "How to apply", "ta": "எப்படி விண்ணப்பிப்பது", "hi": "आवेदन कैसे करें"},
    "official": {"en": "Official website", "ta": "அதிகாரப்பூர்வ இணையதளம்", "hi": "आधिकारिक वेबसाइट"},
    "choose_one": {"en": "⚠️ You can get only one of: {names}", "ta": "⚠️ இவற்றில் ஒன்றை மட்டுமே பெற முடியும்: {names}", "hi": "⚠️ इनमें से केवल एक मिल सकती है: {names}"},
    "unverified": {"en": "ℹ️ Details are being verified against the official source.", "ta": "ℹ️ விவரங்கள் அதிகாரப்பூர்வ தகவலுடன் சரிபார்க்கப்படுகின்றன.", "hi": "ℹ️ विवरण आधिकारिक स्रोत से सत्यापित किए जा रहे हैं।"},
    "error": {"en": "⚠️ The service is temporarily unavailable. Please try again.", "ta": "⚠️ சேவை தற்காலிகமாகக் கிடைக்கவில்லை. மீண்டும் முயற்சிக்கவும்.", "hi": "⚠️ सेवा अभी उपलब्ध नहीं है। कृपया फिर से कोशिश करें।"},
    "stt_fail": {"en": "🎙️ I couldn't hear that clearly. Please type it, or use the buttons.", "ta": "🎙️ சரியாகக் கேட்கவில்லை. தட்டச்சு செய்யவும் அல்லது பொத்தான்களைப் பயன்படுத்தவும்.", "hi": "🎙️ साफ़ सुनाई नहीं दिया। कृपया टाइप करें या बटन दबाएँ।"},
    "too_long": {"en": "Please send a shorter voice note (under {s} seconds).", "ta": "தயவுசெய்து {s} வினாடிக்குள் குரல் செய்தி அனுப்பவும்.", "hi": "कृपया {s} सेकंड से छोटा वॉइस नोट भेजें।"},
    "other_type": {"en": "Please send a text message or a voice note 🙂", "ta": "தயவுசெய்து உரை அல்லது குரல் செய்தி அனுப்பவும் 🙂", "hi": "कृपया टेक्स्ट या वॉइस नोट भेजें 🙂"},
    "reset_done": {"en": "🔄 Starting fresh.", "ta": "🔄 புதிதாகத் தொடங்குகிறோம்.", "hi": "🔄 नई शुरुआत।"},
    "voice_on": {"en": "🔊 Voice replies ON", "ta": "🔊 குரல் பதில்கள் இயக்கத்தில்", "hi": "🔊 आवाज़ में जवाब चालू"},
    "voice_off": {"en": "🔇 Voice replies OFF", "ta": "🔇 குரல் பதில்கள் நிறுத்தப்பட்டன", "hi": "🔇 आवाज़ में जवाब बंद"},
    "profile_title": {"en": "📋 What I know about you", "ta": "📋 உங்களைப் பற்றி எனக்குத் தெரிந்தவை", "hi": "📋 आपके बारे में जानकारी"},
    "inferred": {"en": "inferred", "ta": "ஊகம்", "hi": "अनुमान"},
    "profile_empty": {"en": "Nothing yet — tell me about yourself.", "ta": "இன்னும் எதுவும் இல்லை — உங்களைப் பற்றிச் சொல்லுங்கள்.", "hi": "अभी कुछ नहीं — अपने बारे में बताइए।"},
    "hints_title": {"en": "🌱 Coming up for your family", "ta": "🌱 உங்கள் குடும்பத்துக்கு வரவிருப்பவை", "hi": "🌱 आपके परिवार के लिए आगे"},
    "report_caption": {
        "en": "📑 Your scheme report: reasons, documents and how to apply. Print it or show it at the Common Service Centre (CSC).",
        "ta": "📑 உங்கள் திட்ட அறிக்கை: காரணங்கள், ஆவணங்கள், விண்ணப்பிக்கும் முறை. அச்சிட்டு அல்லது இ-சேவை மையத்தில் காட்டலாம்.",
        "hi": "📑 आपकी योजना रिपोर्ट: कारण, दस्तावेज़ और आवेदन का तरीका। प्रिंट करें या जन सेवा केंद्र (CSC) पर दिखाएँ।",
    },
    "stale": {"en": "That question has expired.", "ta": "அந்தக் கேள்வி காலாவதியாகிவிட்டது.", "hi": "वह सवाल अब मान्य नहीं है।"},
    "help": {
        "en": "<b>How to use Urimai</b>\nJust tell me about yourself by text or 🎙️ voice note. I'll ask a few questions and show schemes you may be eligible for, with reasons, documents and how to apply.\n\n/schemes – your scheme list\n/docs – documents checklist\n/report – PDF report to print or share\n/profile – what I know about you\n/voice – voice replies on/off\n/lang – change language\n/reset – start again",
        "ta": "<b>உரிமையைப் பயன்படுத்துவது எப்படி</b>\nஉங்களைப் பற்றி உரை அல்லது 🎙️ குரல் செய்தியில் சொல்லுங்கள். சில கேள்விகள் கேட்டு, உங்களுக்குக் கிடைக்கக்கூடிய திட்டங்களை — காரணம், ஆவணங்கள், விண்ணப்ப முறையுடன் — காட்டுவேன்.\n\n/schemes – திட்டப் பட்டியல்\n/docs – ஆவணப் பட்டியல்\n/report – அச்சிட / பகிர PDF அறிக்கை\n/profile – உங்களைப் பற்றிய தகவல்\n/voice – குரல் பதில் ஆன்/ஆஃப்\n/lang – மொழி மாற்ற\n/reset – மீண்டும் தொடங்க",
        "hi": "<b>उरिमै कैसे इस्तेमाल करें</b>\nअपने बारे में टेक्स्ट या 🎙️ वॉइस नोट में बताइए। मैं कुछ सवाल पूछकर आपके लिए संभावित योजनाएँ — कारण, दस्तावेज़ और आवेदन तरीके के साथ — दिखाऊँगा।\n\n/schemes – योजनाओं की सूची\n/docs – दस्तावेज़ सूची\n/report – प्रिंट/शेयर के लिए PDF रिपोर्ट\n/profile – आपकी जानकारी\n/voice – आवाज़ में जवाब चालू/बंद\n/lang – भाषा बदलें\n/reset – फिर से शुरू करें",
    },
}


# Bot profile text set via the Bot API at startup. Telegram picks the version by the user's app language;
# "" is the default for everyone else. Most Tamil speakers run Telegram in English, so the default is bilingual.
# Limits: description 512 characters (empty-chat screen), short description 120 (profile page and share links).
BOT_DESCRIPTION = {
    "": (
        "உங்களுக்குக் கிடைக்கக்கூடிய அரசு நலத் திட்டங்களைக் கண்டறியுங்கள்.\n"
        "Find government welfare schemes you may be eligible for.\n\n"
        "🎙️ Talk or type in தமிழ், English or हिंदी: your age, district, work and family income.\n"
        "✅ See central and Tamil Nadu schemes that look likely for you, with documents and where to apply.\n\n"
        "🔒 Never asks for Aadhaar, phone or bank numbers.\n"
        "⚖️ Indicative only. The government department makes the final decision."
    ),
    "en": (
        "Find government welfare schemes you may be eligible for.\n\n"
        "🎙️ Send a voice note or type in Tamil, English or Hindi: your age, district, work and family income.\n"
        "✅ See which central and Tamil Nadu schemes look likely for you, the documents you need and where to apply.\n"
        "👆 Answer a few quick questions with one tap.\n\n"
        "🔒 Never asks for Aadhaar, phone or bank numbers.\n"
        "⚖️ Indicative only. The government department makes the final decision."
    ),
    "ta": (
        "உங்களுக்குக் கிடைக்கக்கூடிய அரசு நலத் திட்டங்களைக் கண்டறியுங்கள்.\n\n"
        "🎙️ தமிழ், ஆங்கிலம் அல்லது இந்தியில் பேசுங்கள் அல்லது எழுதுங்கள்: உங்கள் வயது, மாவட்டம், வேலை, குடும்ப வருமானம்.\n"
        "✅ உங்களுக்குக் கிடைக்க வாய்ப்புள்ள மத்திய, தமிழ்நாடு அரசுத் திட்டங்கள், தேவையான ஆவணங்கள், விண்ணப்பிக்கும் இடம்.\n"
        "👆 சில கேள்விகளுக்கு ஒரே தட்டலில் பதில்.\n\n"
        "🔒 ஆதார், தொலைபேசி, வங்கி எண்களைக் கேட்பதில்லை.\n"
        "⚖️ இது தோராயமான தகவல் மட்டுமே. இறுதி முடிவு அரசுத் துறையுடையது."
    ),
    "hi": (
        "जानिए कौन-सी सरकारी कल्याण योजनाएँ आपको मिल सकती हैं।\n\n"
        "🎙️ तमिल, अंग्रेज़ी या हिंदी में बोलें या लिखें: अपनी उम्र, ज़िला, काम और परिवार की आय।\n"
        "✅ देखें कि कौन-सी केंद्र और तमिलनाडु सरकार की योजनाएँ आपके लिए संभावित हैं, कौन-से दस्तावेज़ चाहिए और कहाँ आवेदन करें।\n"
        "👆 कुछ आसान सवालों के जवाब एक टैप में।\n\n"
        "🔒 आधार, फ़ोन या बैंक नंबर कभी नहीं माँगता।\n"
        "⚖️ केवल अनुमान। अंतिम निर्णय संबंधित सरकारी विभाग का होगा।"
    ),
}
BOT_SHORT_DESCRIPTION = {
    "": "அரசுத் திட்டங்களைக் கண்டறியுங்கள் · Find government schemes you may be eligible for. Tamil, English, Hindi.",
    "en": "Find government welfare schemes you may be eligible for. Talk in Tamil, English or Hindi, by voice or text.",
    "ta": "உங்களுக்குக் கிடைக்கக்கூடிய அரசு நலத் திட்டங்களைக் கண்டறியுங்கள். குரல் அல்லது எழுத்தில் பேசுங்கள்.",
    "hi": "जानिए कौन-सी सरकारी योजनाएँ आपको मिल सकती हैं। तमिल, अंग्रेज़ी या हिंदी में, बोलकर या लिखकर।",
}


def t(key: str, lang: str, **kw) -> str:
    d = S[key]
    s = d.get(lang) or d["en"]
    return s.format(**kw) if kw else s
