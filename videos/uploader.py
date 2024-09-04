#!/usr/bin/env python3

import json, os, sys, subprocess, time
from datetime import datetime, UTC

def ensure_venv():
    if 'VIRTUAL_ENV' not in os.environ:
        need_install = False
        if not os.path.isdir(".venv"):
            subprocess.check_call(["python3", "-m", "venv", ".venv"])
            need_install = True
        os.environ['VIRTUAL_ENV_PROMPT'] = '(.venv) '
        os.environ['VIRTUAL_ENV'] = os.path.join(os.getcwd(), ".venv")
        for cur in ["Scripts", "bin"]:
            if os.path.isdir(os.path.join(os.getcwd(), ".venv", cur)):
                venv_path = os.path.join(os.getcwd(), ".venv", cur)
                break
        for cur in ["python", "python.exe"]:
            if os.path.isfile(os.path.join(venv_path, cur)):
                venv_file = os.path.join(venv_path, cur)
                break
        os.environ['PATH'] = venv_path + (";" if ";" in os.environ['PATH'] else ":") + os.environ['PATH']
        if need_install:
            subprocess.call(["pip", "install", "-r", "requirements.txt"])
        exit(subprocess.call([venv_file] + sys.argv))

def upload_next():
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.http import MediaFileUpload
    import google.oauth2.credentials
    import googleapiclient.discovery

    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    with open(os.path.join("..", "output", "daily.json")) as f:
        daily = json.load(f)
    at = None
    for key, value in daily.items():
        if 'youtube' not in value:
            at = key
            break
    if at is None:
        print("Unable to find video!")
        return False

    api_service_name = "youtube"
    api_version = "v3"

    saved_creds_fn = os.path.join(os.path.expanduser("~"), ".youtube", "saved_creds.json")

    if os.path.isfile(saved_creds_fn):
        with open(saved_creds_fn) as f:
            temp = json.load(f)
        creds = google.oauth2.credentials.Credentials.from_authorized_user_info(temp)
    else:
        flow = Flow.from_client_secrets_file(
            os.path.join(os.path.expanduser("~"), ".youtube", "secrets_file.json"),
            scopes=['https://www.googleapis.com/auth/youtube.upload'],
            redirect_uri='http://localhost')
        auth_url, _ = flow.authorization_url(prompt='consent')
        print('Please go to this URL: {}'.format(auth_url))
        code = input('Enter the authorization code: ')
        flow.fetch_token(code=code)
        creds = flow.credentials
        with open(saved_creds_fn, "wt") as f:
            f.write(creds.to_json())

    youtube = googleapiclient.discovery.build(
        api_service_name, api_version,  credentials=creds)

    now = datetime.now(UTC).strftime("%d %H:%M:%S")
    print(f"{now}: Uploading {at}: {daily[at]['theme']}, ", end="", flush=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": f"Vertex for {at}: {daily[at]['theme']}",
            },
            "status": {
                "privacyStatus": "unlisted"
            },
        },
        media_body=MediaFileUpload(os.path.join(*(["..", "output"] + daily[at]['video'].split("/"))))
    )
    response = request.execute()
    print("Uploaded: " + response['id'])
    if "UPLOAD_HELPER" in os.environ:
        try:
            subprocess.call([os.environ["UPLOAD_HELPER"], f"Uploaded {at}: {daily[at]['theme']}, as {response['id']}"])
        except:
            pass
    daily[at]['youtube'] = response['id']
    with open(os.path.join("..", "output", "daily.json"), "wt", newline="", encoding="utf-8") as f:
        json.dump(daily, f, indent=4)
        f.write("\n")
    return True

def main():
    ensure_venv()

    while True:
        try:
            status = upload_next()
            to_sleep = 0.5
        except Exception as e:
            print(f"ERROR: {e}")
            to_sleep = 8
            status = True
        if not status:
            break
        print(f"Sleeping for {to_sleep:.1f} hours...")
        time.sleep(3600 * to_sleep)

if __name__ == "__main__":
    main()
