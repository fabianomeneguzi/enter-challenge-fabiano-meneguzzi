require('dotenv').config();
const { runGraph, loadProjectFromFile } = require('@ironclad/rivet-node');
const fs = require('fs');

function resolveClientId() {
    const fromArg = process.argv[3];
    if (fromArg) return fromArg;
    const raw = fs.readFileSync('clients.json', 'utf-8');
    const clients = JSON.parse(raw);
    if (!clients.length) {
        console.error('clients.json has no clients; pass client_id as 3rd argument.');
        process.exit(1);
    }
    return clients[0].id;
}

function clientFileInputs(clientId) {
    const clients = JSON.parse(fs.readFileSync('clients.json', 'utf-8'));
    const c = clients.find((x) => x.id === clientId);
    if (!c) {
        console.error(`Client '${clientId}' not found in clients.json`);
        process.exit(1);
    }
    const macro = c.macro_file || 'XP - Macro analysis.txt';
    return {
        portfolio_file_path: { type: 'string', value: c.portfolio_file },
        risk_file_path: { type: 'string', value: c.risk_file },
        macro_file_path: { type: 'string', value: macro },
    };
}

async function main() {
    if (!process.env.OPENAI_API_KEY) {
        console.error("Error: OPENAI_API_KEY not found in .env!");
        process.exit(1);
    }

    const graphToRun = process.argv[2];
    if (!graphToRun) {
        console.error("Error: No graph specified. Usage: node run_workflows.js <graph_name> [client_id]");
        process.exit(1);
    }

    const clientId = resolveClientId();
    const fileInputs = clientFileInputs(clientId);
    console.log(`Using client_id=${clientId}`);

    console.log("Loading Rivet project...");
    const project = await loadProjectFromFile('Enter Challenge.rivet-project');

    if (!fs.existsSync("outputs")) {
        fs.mkdirSync("outputs");
    }

    if (graphToRun === "extract_positions") {
        console.log("\nExecuting 'extract_positions' graph...");
        try {
            const result = await runGraph(project, {
                graph: "extract_positions",
                openAiKey: process.env.OPENAI_API_KEY,
                inputs: {
                    portfolio_file_path: fileInputs.portfolio_file_path,
                },
            });

            let positionsResult = "";
            if (result && result.output) {
                positionsResult = result.output.value;
                if (typeof positionsResult === 'string') {
                    positionsResult = positionsResult.replace(/```json/g, '').replace(/```/g, '').trim();
                }
            }

            fs.writeFileSync("outputs/positions.json", positionsResult || "{}");
            console.log("Positions JSON saved at outputs/positions.json");
        } catch (err) {
            console.error("Error executing extract_positions:", err);
            process.exit(1);
        }
    }
    else if (graphToRun === "extract_riskprofile") {
        console.log("\nExecuting 'extract_riskprofile' graph...");
        try {
            const result = await runGraph(project, {
                graph: "extract_riskprofile",
                openAiKey: process.env.OPENAI_API_KEY,
                inputs: {
                    risk_file_path: fileInputs.risk_file_path,
                },
            });

            let profileResult = "";
            if (result && result.output) {
                profileResult = result.output.value;
                if (typeof profileResult === 'string') {
                    profileResult = profileResult.replace(/```json/g, '').replace(/```/g, '').trim();
                }
            }

            fs.writeFileSync("outputs/risk_profile.json", profileResult || '{"profile": "Moderate"}');
            console.log("Risk profile JSON saved at outputs/risk_profile.json");
        } catch (err) {
            console.error("Error executing extract_riskprofile:", err);
            process.exit(1);
        }
    }
    else if (graphToRun === "main_challenge") {
        console.log("\nExecuting 'main_challenge' graph...");

        let performanceData = {};
        if (fs.existsSync("outputs/performance_summary.json")) {
            console.log("Reading performance_summary.json to inject into workflow...");
            performanceData = JSON.parse(fs.readFileSync("outputs/performance_summary.json", "utf-8"));
        } else {
            console.warn("Warning: outputs/performance_summary.json not found.");
        }

        let macroData = {};
        if (fs.existsSync("outputs/macro_news.json")) {
            console.log("Reading macro_news.json to inject into workflow...");
            macroData = JSON.parse(fs.readFileSync("outputs/macro_news.json", "utf-8"));
        }

        let recData = {};
        if (fs.existsSync("outputs/recommendations.json")) {
            console.log("Reading recommendations.json to inject into workflow...");
            recData = JSON.parse(fs.readFileSync("outputs/recommendations.json", "utf-8"));
        }

        try {
            const result = await runGraph(project, {
                graph: "main_challenge",
                openAiKey: process.env.OPENAI_API_KEY,
                inputs: {
                    performance_data: { type: "object", value: performanceData },
                    macro_outlook: { type: "object", value: macroData },
                    recommendations: { type: "object", value: recData },
                    portfolio_file_path: fileInputs.portfolio_file_path,
                    risk_file_path: fileInputs.risk_file_path,
                    macro_file_path: fileInputs.macro_file_path,
                },
            });

            let letterData = { portfolio: "", macro_and_risk: "", greeting: "" };
            if (result && result.output && result.output.value) {
                letterData = result.output.value;
            }

            fs.writeFileSync("outputs/letter.json", JSON.stringify(letterData, null, 2));
            console.log("Letter data saved at outputs/letter.json");

        } catch (err) {
            console.error("Error executing main_challenge:", err);
            process.exit(1);
        }
    }
    else {
        console.error(`Error: Unknown graph '${graphToRun}'`);
        process.exit(1);
    }
}

main();
