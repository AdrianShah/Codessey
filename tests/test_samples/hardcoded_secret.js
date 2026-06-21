const axios = require('axios');

// Hardcoded API keys — should be in environment variables
const API_KEY = "AIzaSyA1234567890abcdefghijklmnopqrstuvwx";
const AWS_KEY = "AKIAIOSFODNN7EXAMPLE";
const STRIPE_KEY = "sk-test-1234567890abcdefghijklmnop";
const GITHUB_TOKEN = "ghp_1234567890abcdefghijklmnopqrstuvwxyz";

async function fetchData(endpoint) {
    const response = await axios.get(endpoint, {
        headers: {
            'Authorization': `Bearer ${API_KEY}`,
            'X-AWS-Key': AWS_KEY,
        }
    });
    return response.data;
}

function buildQuery(userInput) {
    // SQL injection vulnerability
    return `SELECT * FROM users WHERE name = '${userInput}'`;
}

module.exports = { fetchData, buildQuery };
