from slackclient import SlackClient
import requests
import os
from PIL import Image, ImageDraw
import json
import io
from lxml import html
from datetime import datetime
import inflect

script_dir = os.path.dirname(__file__)

class do:
    def post_message(sc, message, channel):
        sc.api_call("chat.postMessage", channel=channel, text=message)

    def get_channels(sc):
        channels = {}
        data = sc.api_call("channels.list")
        for item in data["channels"]:
            channels[item["name"]] = item["id"]
        return channels

    def get_messages(sc, channel_id, ts):
        messages = []
        timestamps = []
        data = sc.api_call("channels.history", channel=channel_id, oldest=ts)
        if len(data["messages"]) > 0:
            for item in data["messages"]:
                if "bot_id" not in item:
                    messages.append({"user": item["user"], "message": item["text"]})
                timestamps.append(float(item["ts"]))
            latest_ts = str(max(timestamps)+0.5)

        else:
            latest_ts = ts

        return messages, latest_ts

    def post_with_attachment(sc, title, img, channel):
        sc.api_call("chat.postMessage", channel=channel, attachments=[{"title":title, "image_url": img}])

    def check_for_file(sc, title):
        files = sc.api_call("files.list")
        for file in files["files"]:
            if file["title"].upper() == title.upper():
                return file["url_private"]
        return None

    def get_latest_message(sc, channel_id):
        message = {}
        data = sc.api_call("channels.info", channel=channel_id)
        if "username" not in data["channel"]["latest"]:
            message["user"] = data["channel"]["latest"]["user"]
        else:
            message["user"] = data["channel"]["latest"]["username"]
        message["message"] = data["channel"]["latest"]["text"]
        return message

    def get_package(provider, url):
        try:
            if provider == "bring":
                delivered = False
                return_data = []
                r = requests.get(url, timeout=0.5)
                if "error" in r.json()["consignmentSet"][0]:
                    return("404", delivered)

                data = r.json()["consignmentSet"][0]["packageSet"][0]["eventSet"]
                delivered = (data[0]["status"].lower() == "delivered")
                for item in data:
                    return_data.append("{0} {1} - {2}".format(item["displayDate"].replace(".", "/"), item["displayTime"], item["description"]))
                return(return_data, delivered)

            if provider == "gls":
                delivered = False
                return_data = []
                r = requests.get(url, timeout=0.5)
                if r.status_code == 404:
                    return("404", delivered)

                data = r.json()["tuStatus"][0]["history"]
                delivered = (r.json()["tuStatus"][0]["progressBar"]["statusInfo"].lower() == "delivered")
                for item in data:
                    return_data.append("{0} {1} - {2}".format(item["date"], item["time"], item["evtDscr"]))
                return(return_data, delivered)

            if provider == "postnord":
                delivered = False
                return_data = []
                r = requests.get(url, timeout=0.5)
                if len(r.json()["response"]["trackingInformationResponse"]["shipments"]) == 0:
                    return("404", delivered)

                data = r.json()["response"]["trackingInformationResponse"]["shipments"][0]["items"][0]["events"]
                delivered = (r.json()["response"]["trackingInformationResponse"]["shipments"][0]["status"].lower() == "delivered")
                for item in data:
                    return_data.append("{0} - {1}".format(item["eventTime"].replace("T", " "), item["eventDescription"]))
                return(return_data, delivered)
        except Exception as e:
            return(None, False)

    def find_room(room):
        with open(os.path.join(script_dir, "locations.json"), "r") as f:
            locations = json.load(f)

        if room.upper() not in locations:
            return None

        x, y = locations[room.upper()]
        img = Image.open(os.path.join(script_dir, "{0}.png".format(room.upper()[0:2])))
        draw = ImageDraw.Draw(img)
        draw.ellipse([x-10, y-10, x+10, y+10], fill="#ff0000")
        img.save(os.path.join(script_dir, "temp.png"), "PNG")
        return os.path.join(script_dir, "temp.png")

    def upload_file(sc, filepath, channel, title):
        with open(filepath, "rb") as f:
            sc.api_call(
                "files.upload",
                channels=channel,
                filename=os.path.split(filepath),
                title=title,
                file=io.BytesIO(f.read()))

    def get_menu():
        url = 'https://iss.inmsystems.com/TakeAway/telenoraal789/Main/Products/1'
        p = inflect.engine()
        """Return the content of the website on the given url in
        a parsed lxml format that is easy to query."""

        response = requests.get(url)
        parsed_page = html.fromstring(response.content)
        menu_raw = json.loads("".join(parsed_page.xpath("//div[@id='content']/input/@value")))


        menu = {}

        for item in menu_raw:
            if item["description"] != "":
                if "suppe" in item["name"].lower():
                    name = "Soup"
                elif "varme" in item["name"].lower():
                    name = "Buffet"
                else:
                    name= item["name"]

                if item["date"] not in menu:
                    menu[item["date"]] = {}
                menu[item["date"]][name] = "• " + item["description"].strip()

        parsed_menu = []

        keylist = list(menu.keys())
        keylist.sort()
        for key in keylist:
            menu_date = datetime.strptime(key, '%Y%m%d')
            menu_items = []
            for k, v in menu[key].items():
                menu_items.append(v)
            parsed_menu.append("*{0}:*\n{1}".format("{0} the {1}".format(menu_date.strftime("%A"), p.ordinal(menu_date.day)), "\n".join(menu_items)))

        return("\n\n".join(parsed_menu))




if __name__ == "__main__":
    print(do.get_package("bring", "https://tracking.bring.com/api/v2/tracking.json?q=70300492378272538"))
