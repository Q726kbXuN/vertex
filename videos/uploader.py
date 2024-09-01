#!/usr/bin/env python3

import os
import googleapiclient.discovery
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import Flow
import google.oauth2.credentials
import json
import time

def upload_next():
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

    print(f"Uploading {at}: {daily[at]['theme']}, ", end="", flush=True)
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
    daily[at]['youtube'] = response['id']
    with open(os.path.join("..", "output", "daily.json"), "wt", newline="", encoding="utf-8") as f:
        json.dump(daily, f, indent=4)
        f.write("\n")
    return True

def main():
    while True:
        try:
            status = upload_next()
        except Exception as e:
            print(f"ERROR: {e}")
            status = True
        if not status:
            break
        print("Sleeping for an hour...")
        time.sleep(3600)

if __name__ == "__main__":
    main()
