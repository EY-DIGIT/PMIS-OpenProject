# Testing the API - Step by Step Guide

## 🎯 For User "Chinmaya"

You've registered a user named "Chinmaya". Here's how to test the GET user API.

---

## Step 1: Find Chinmaya's User ID

### Option A: Using the browser (EASIEST)

1. **Start the server** (if not already running):
   ```bash
   cd user_service
   START_SERVER.bat
   ```

2. **Open browser**: http://localhost:8000/api/docs

3. **Find the "GET /api/v3/users" endpoint** (scroll down to "users" section)

4. **Click "Try it out"**

5. **Click "Execute"** - This lists all users

6. **Look for Chinmaya in the response** - You'll see something like:
   ```json
   {
     "_embedded": {
       "elements": [
         {
           "id": 123456,  ← THIS IS THE USER ID
           "login": "Chinmaya",
           "name": "Chinmaya",
           ...
         }
       ]
     }
   }
   ```

7. **Copy the ID number** (e.g., 123456)

### Option B: Using curl

```bash
curl http://localhost:8000/api/v3/users
```

Look for the `"id"` field in the response.

---

## Step 2: Get User by ID

Now that you have the ID, you can test the GET user endpoint:

### Using the Interactive Docs (http://localhost:8000/api/docs)

1. **Find "GET /api/v3/users/{user_id}"** endpoint

2. **Click "Try it out"**

3. **Enter the user_id**: Type the ID you found (e.g., `123456`)
   - ⚠️ **ONLY enter the number** - don't add quotes or anything else
   - Example: `123456` ✅
   - NOT: `"123456"` ❌
   - NOT: `user_id=123456` ❌

4. **Click "Execute"**

5. **See the response** - You should get Chinmaya's user data!

Expected response:
```json
{
  "_type": "User",
  "id": 123456,
  "login": "Chinmaya",
  "firstName": "...",
  "lastName": "...",
  "name": "Chinmaya",
  "email": "...",
  "admin": false,
  "status": "registered",
  "language": "en",
  "createdAt": "2025-12-05T...",
  "updatedAt": "2025-12-05T...",
  "_links": {
    "self": {
      "href": "/api/v3/users/123456"
    }
  }
}
```

---

## Step 3: Test with curl (Alternative)

If you prefer command line:

```bash
# Replace 123456 with actual user ID
curl http://localhost:8000/api/v3/users/123456

# For formatted output:
curl http://localhost:8000/api/v3/users/123456 | python -m json.tool
```

---

## 🎯 Quick Reference Card

### All User Endpoints

| What | Endpoint | Example |
|------|----------|---------|
| **List all users** | `GET /api/v3/users` | Lists Chinmaya and others |
| **Get user by ID** | `GET /api/v3/users/{id}` | Get Chinmaya's details |
| **Get current user** | `GET /api/v3/users/me` | If logged in |
| **Update user** | `PATCH /api/v3/users/{id}` | Update Chinmaya |
| **Delete user** | `DELETE /api/v3/users/{id}` | Delete Chinmaya |
| **Lock user** | `POST /api/v3/users/{id}/lock` | Lock Chinmaya |
| **Unlock user** | `POST /api/v3/users/{id}/unlock` | Unlock Chinmaya |

---

## ❓ Troubleshooting

### "user_id, args, kwargs are required"

✅ **FIXED!** The API docs should now show only `user_id` as required, with a clear description.

If you still see issues:
1. **Restart the server** to load the updated code
2. **Refresh the browser** at http://localhost:8000/api/docs
3. The parameter should now show: `user_id` with description "User ID or 'me' for current user"

### "404 Not Found"

- The user ID doesn't exist
- Solution: List all users first to find the correct ID

### "401 Unauthorized"

- Some endpoints require authentication
- Solution: Login first or use a public endpoint

---

## 📋 Testing Checklist

- [ ] Server is running (http://localhost:8000)
- [ ] Opened API docs (http://localhost:8000/api/docs)
- [ ] Listed all users (GET /api/v3/users)
- [ ] Found Chinmaya's user ID
- [ ] Got user by ID (GET /api/v3/users/{id})
- [ ] Saw Chinmaya's full user data

---

## 💡 Pro Tips

### Tip 1: Use "me" endpoint

If you're logged in as Chinmaya, you can use:
```
GET /api/v3/users/me
```
Instead of finding the ID!

### Tip 2: Use the browser

The interactive docs at `/api/docs` are the easiest way to test:
- No command line needed
- Shows all parameters
- Formats responses nicely
- Has "Try it out" for instant testing

### Tip 3: Check the server logs

The server prints logs when you make requests. Look for:
```
INFO:     127.0.0.1:xxxxx - "GET /api/v3/users/123456 HTTP/1.1" 200 OK
```

---

## 🎉 Success!

When you successfully get a user, you should see:
- ✅ HTTP 200 OK status
- ✅ User data with all fields
- ✅ HAL+JSON format with `_type` and `_links`
- ✅ Chinmaya's information displayed

**You're now ready to use the API!** 🚀

Need more help? See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
