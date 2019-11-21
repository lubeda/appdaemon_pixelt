import appdaemon.plugins.hass.hassapi as hass
import requests
import json

class pixelIT(hass.Hass):

  def load_template(self,name):
    try: 
      fp = open(self.args["path"]+name,"r")
      data = json.load(fp)
      data["screen"] = name.replace(".json","")
      fp.close()
      return data
    except:
      self.log("Template not found: "+name,level = "ERROR")
      return None

  def rest_add(self,kwargs):
    if self.debug: self.log("pixelit_add: " +str(kwargs))
    try:
      data = self.load_template(kwargs["title"]+".json")
      if len(kwargs["message"]) and (kwargs["title"] != "clock"):
        data["text"]["textString"] = kwargs["message"] 
      if kwargs.get("target") != None:
        data["target"] = kwargs["target"]
        if data["target"] == "warning": data["repeat"] *= 2
      self.playlist_add(data)
      response = {"length playlist": len(self.playlist)}
      return response, 200
    except:
      self.log("Unable to add screen",level = "ERROR")
      response = {"error": "message or title missing"}
      return response, 400

  def rest_color(self,kwargs):
    if self.debug: self.log("rest_color: " +str(kwargs))
    try:
      for msg in self.playlist:
        if msg["screen"] == kwargs["title"]:
          msg["text"]["color"]["r"] = kwargs["r"] 
          msg["text"]["color"]["g"] = kwargs["g"]
          msg["text"]["color"]["b"] = kwargs["b"]
      return response, 200
    except:
      self.log("Unable to update color",level = "ERROR")
      response = {"error": "screen not deleted"}

  def rest_sensor(self,kwargs):
    try: 
      r = {}
      r["state"]= len(self.playlist)
      return r, 200
    except:
      self.log("Unable to return sensordata",level = "ERROR")
      return "Error", 400

  def rest_playlist(self,kwargs):
    return self.playlist, 200

  def rest_delete(self,kwargs):
    if self.debug: self.log("rest_delete: "+str(kwargs))
    if self.alertMsg != None:
      if self.debug: self.log("rest_delete: alert")
      if self.alertMsg["screen"] == kwargs["title"]: self.alertMsg = None
    if self.warningMsg != None:
      if self.debug: self.log("rest_delete: warning")
      if self.warningMsg["screen"] == kwargs["title"]: self.warningMsg = None
    try:
      for msg in self.playlist:
        if msg["screen"] == kwargs["title"]:
          self.log("delete found "+ kwargs["title"] + " len: " + str(len(self.playlist)))
          if msg.get("target") == "alert": self.alertMsg = None
          self.playlist.remove(msg)
      response = {"playlist": len(self.playlist)}
      return response, 200
    except:
      self.log("Unable to delete screen",level = "ERROR")
      response = {"error": "screen not deleted"}
      return response, 400  

  def rest_update(self,kwargs):
    found = False
    if self.debug: self.log("rest_update: " + str(kwargs))
    try:
      for msg in self.playlist:
        if msg["screen"] == kwargs["title"]:
          found = True
          for key in kwargs:
            if key=="message":
              msg["text"]["textString"] = kwargs["message"]
            elif key != "title":
              if self.debug: self.log("update key: "+ key +" " + str(kwargs[key]))
              msg[key]= {**msg[key] , **kwargs[key]} 
      response = {"playlist": len(self.playlist)}
      if found:
        return response, 200
      else:
        self.rest_add(kwargs)
        return response, 200
    except:
      self.log("Unable to update screen",level = "ERROR")
      response = {"error": "screen not deleted"}
      return response, 400  

  def initialize(self):
    self.url = 'http://' + self.args["ip"] + '/api/screen'
    self.log(self.url)
    self.playlist= []
    self.debug = True
    self.pointer = 0
    self.showAlert = True
    self.alertMsg = None
    self.warningMsg = None
    self.register_endpoint(self.rest_add, "pixelit_add")
    self.register_endpoint(self.rest_delete, "pixelit_delete")
    self.register_endpoint(self.rest_update, "pixelit_update")
    self.register_endpoint(self.rest_color, "pixelit_color")
    self.register_endpoint(self.rest_sensor, "pixelit_sensor")
    if self.debug: self.register_endpoint(self.rest_playlist, "pixelit_playlist")
    self.nextLoop = self.run_in(self.playlist_loop, 3)

  def display(self,msg):
    if self.debug: self.log("display: " + json.dumps(msg))
    try: 
      r = requests.post(self.url,data=json.dumps(msg), headers={'Content-Type': 'application/data'})
      if self.debug: self.log("display return: " +r.text)
    except:
      self.log("Error while sending to display.",level="ERROR")

  def playlist_add(self,msg):
    try: 
      if msg["seconds"] < 5:
        msg["seconds"] = 5
      if msg.get("target") == "alert":
        if self.debug: self.log("alert: " +msg["text"]["textString"])
        msg["seconds"] = 20
        self.alertMsg = msg
        self.cancel_timer(self.nextLoop)
        self.nextLoop = self.run_in(self.playlist_loop, 1)
      elif msg.get("target") == "warning":
        self.warningMsg = msg
      else:
        self.playlist.append(msg)
    except:
      self.log("Unable to add to playlist",level="ERROR")

  def playlist_loop(self, kwargs):
    
    self.showAlert = not self.showAlert
    if (self.alertMsg is not None) and self.showAlert:
      if self.debug: self.log("Show alert")
      self.display(self.alertMsg)
      self.nextLoop = self.run_in(self.playlist_loop, self.alertMsg["seconds"])
      return
    if (self.warningMsg is not None) and not self.showAlert:
      if self.debug: self.log("Show warning")
      self.display(self.warningMsg)
      if (self.warningMsg["repeat"] > 0): self.warningMsg["repeat"] -= 1
      self.nextLoop = self.run_in(self.playlist_loop, self.warningMsg["seconds"])
      return
    if len(self.playlist) > 0:
      nowPlay = self.pointer
      if nowPlay >= len(self.playlist):
        nowPlay = 0
      if self.debug: self.log("show MSG: "+ self.playlist[nowPlay]["screen"] + " " + str(nowPlay) + "/" +str(len(self.playlist)))
      if (self.playlist[nowPlay]["repeat"] > 0) and (self.playlist[nowPlay]["screen"] != "clock"):
        self.playlist[nowPlay]["repeat"] -= 1

      try:
        status = self.set_state(self.args["entitiy_id"], state =len(self.playlist) , attributes = {"screen": self.playlist[nowPlay]["screen"]})
      except:
        status = None        
      self.display(self.playlist[nowPlay])
      self.nextLoop = self.run_in(self.playlist_loop, self.playlist[nowPlay]["seconds"])
      if self.playlist[nowPlay]["repeat"] == 0:
        if self.debug: self.log("last time: "+self.playlist[nowPlay]["text"]["textString"])
        self.playlist.pop(nowPlay)
        if self.debug: self.log("playlist length =>"+str(len(self.playlist)))
      
      if nowPlay < len(self.playlist):
        nowPlay+=1
      self.pointer = nowPlay
    else:
      self.playlist_add(self.load_template("clock.json"))
      self.nextLoop = self.run_in(self.playlist_loop, 10)