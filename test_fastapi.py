from fastapi import FastAPI, Request
import uvicorn
import asyncio

app = FastAPI()

@app.post("/webhook")
async def webhook(request: Request):
    try:
        raw_body = await request.body()
        print("Body:", raw_body)
    except Exception as e:
        print("Error getting body:", e)
        return {"error": str(e)}

    try:
        event = await request.json()
        print("JSON:", event)
    except Exception as e:
        print("Error getting JSON:", e)
        return {"error": str(e)}

    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
