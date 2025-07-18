import { Command } from "commander";
import { loadConfig } from "../utils/config";

const details = new Command("details")
  .description("Show stored email address")
  .action(() => {
    try {
      const { email } = loadConfig();
      console.log(`Stored email: ${email}`);
    } catch (err) {
      console.error("Not logged in. Run `bernerspace init`.");
    }
  });

export default details;
