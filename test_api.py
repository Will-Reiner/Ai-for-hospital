from google import genai

client = genai.Client(api_key="AIzaSyDIaovQS3-oOT9LXrmygoaclfMWtaccAmY")

response = client.models.generate_content(
    model="gemini-3-flash-preview", contents="Explain how AI works in a few words"
)
print(response.text)
