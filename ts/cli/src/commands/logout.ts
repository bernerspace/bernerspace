import { Command } from "commander";
import fs from "fs";
import os from "os";
import path from "path";

const logout = new Command("logout")
  .description("Remove saved token and email from config")
  .action(() => {
    const configDir = path.join(os.homedir(), ".bernerspace");
    const configFile = path.join(configDir, "config.json");
    if (fs.existsSync(configFile)) {
      fs.unlinkSync(configFile);
      console.log("Logged out; credentials removed.");
    } else {
      console.log("No credentials found.");
    }
  });

export default logout;
