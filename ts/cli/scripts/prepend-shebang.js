#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

// Ensure dist/main.js starts with the proper shebang
const file = path.join(__dirname, "../dist/main.js");
if (fs.existsSync(file)) {
  let content = fs.readFileSync(file, "utf8");
  if (!content.startsWith("#!")) {
    const shebang = "#!/usr/bin/env node\n";
    content = shebang + content;
    fs.writeFileSync(file, content, "utf8");
    fs.chmodSync(file, 0o755);
  }
}
