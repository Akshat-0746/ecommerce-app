function formatPrice(price) {
    return "$" + Number(price).toFixed(2);
}

// Fetch JSON from our API. If the server replies with an error status
// (400, 404, ...), turn the server's error message into a thrown Error.
async function fetchJSON(url) {
    const response = await fetch(url);
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || `Request failed (${response.status})`);
    }
    return data;
}