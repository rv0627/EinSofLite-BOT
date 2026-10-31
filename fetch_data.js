const fetch = require('node-fetch');
async function run() {
  const res = await fetch('http://localhost:8001/api/analytics/INFY?interval=D');
  const data = await res.json();
  console.log(JSON.stringify(data.rawOHLCV.slice(0, 5), null, 2));
}
run();
