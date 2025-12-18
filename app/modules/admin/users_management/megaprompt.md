

Role & Objective:
You are a Senior Frontend Architect and specialized UI/UX Designer for Enterprise Applications. You are tasked with building the Hoviat Admin Panel, a high-performance, RTL (Right-to-Left) web application using Next.js 15.

CRITICAL INSTRUCTION: Do not hallucinate APIs. Use ONLY the specific endpoints, JSON structures, and logic defined in this document. Do not summarize this prompt; implement every detail strictly.

PART 1: TECHNOLOGY STACK & ARCHITECTURE

1. Core Framework

Framework: Next.js 15 (App Router).

Language: TypeScript (Strict Mode).

Styling: Tailwind CSS + Shadcn UI.

Icons: Lucide React.

Fonts: Vazirmatn (Google Font) for all text.

Direction: The entire app is dir="rtl".

2. State Management & Data Fetching

TanStack Query (v5): Use this for ALL API calls.

URL-Driven State (The Golden Rule): You must NOT rely solely on local React state for filters or pagination. The URL is the source of truth.

Behavior: If I filter the list, then click into a user's details, then click "Back", I must return to the exact same filtered state.

Implementation: Use useSearchParams to sync state to the URL.

3. "Screaming Architecture" (Folder Structure)
Organize files by FEATURE, not by type.

code
Text
download
content_copy
expand_less
/src
  /app
    /(auth)/login/page.tsx
    /(dashboard)/layout.tsx  (Sidebar + Header)
    /(dashboard)/users/page.tsx
    /(dashboard)/users/[id]/page.tsx
  /features
    /auth
      /api, /components, /hooks, /types
    /users
      /api (Axios calls)
      /components (UserCard, UserRow, DynamicFilter, EditUserModal)
      /hooks (useUsers, useUser)
      /types
  /lib
    axios.ts (Global config)
PART 2: DESIGN SYSTEM - "FUTURE CORPORATE LIQUID"

1. The Atmosphere

Background: NOT plain white. It must be "Clean Corporate White" with a subtle "cloudy and granity" texture/noise to give it depth and a high-end feel.

Glass Physics (Performance Critical):

The UI relies heavily on "Liquid Glass" (glassy boxes with round corners that glow white/brighten the background).

Constraint: Heavy glass blur lags on moving objects. You must implement two separate CSS classes:

.glass-static: High blur (16px+), high transparency, reflective white borders. Use for: Cards, Modals, Sidebar, Header.

.glass-moving: Low blur (4px-6px), higher opacity. Use for: Animations, Floating Buttons, anything that moves.

2. Color Palette & Materials

Gold (The Accent): Used for Tools, Floating Action Buttons (FAB), "Apply" buttons.

Texture: Must look like a "shiny object made of gold" or "shiny gold paper."

Silver: Used specifically for Field Names/Labels.

Black: Used specifically for Field Values.

3. Layout Shell

Header: Glassy. Top Right (visually Left in RTL) = "Home" button. Top Left = "Logout".

Dashboard: A grid of 4 Glassy Boxes (Mobile: 2 columns).

Box 1 (Active): "مدیریت کاربران" (User Management). Bold title, small description.

Box 2, 3, 4 (Disabled): "Workflows", "Stats", "AI". These are "Coming Soon" - they are unclickable and have a gray "See-through" layer over them to feel "off".

PART 3: AUTHENTICATION (REAL API)

Login Page:

UI: A centered, glassy card on the granity background.

API Logic:

Endpoint: POST https://hoviat-admin-fast-api.onrender.com/api/admin/auth/login

Headers: Content-Type: application/x-www-form-urlencoded

Payload: username, password

Response Handling:

Success (200):

code
JSON
download
content_copy
expand_less
{
    "access_token": "eyJhbGciOiJIUzI1Ni...",
    "token_type": "bearer",
    "expires_in": 604800,
    "username": "bardia",
    "is_superadmin": true
}

Action: Store token in localStorage. Redirect to Dashboard.

Error (401): Display "Invalid credentials".

Global Axios Configuration (lib/axios.ts):

Request Interceptor: Append Authorization: Bearer <token> to every request.

Response Interceptor (CRITICAL):

If 403 (Forbidden): Do NOT redirect. Display a "Permission Denied" Toast notification (use Shadcn Sonner/Toast). The user stays where they are.

If 401 (Unauthorized): Redirect to /login.

PART 4: USER MANAGEMENT (THE CORE FEATURE)

Route: /users

1. The Views (Toggleable via Toolbar)
You must provide two distinct views to display the user list.

View A: Card View (Glassy Boxes)

Visual: A grid of cards.

Content:

Profile Picture (Large Circle, centered).

First Name + Last Name.

Telegram ID.

Country.

Badge: If is_ban === true, show a Warning Badge in the top corner.

View B: List/Row View (The "Custom" Table)

Structure: NOT a standard HTML <table>.

Visual: A stack of long, horizontal glass rectangles. Each row has a margin separating it from the next.

Content Layout:

Right Side: Small Square Profile Picture.

Flowing Left: Key data points (Name, ID, Phone, Country, Score, Status).

Exclusions: Do NOT show technical fields like mode, accounting_code, profile_path in this view.

2. The Dynamic Filter Engine (Highest Complexity)

Trigger: A Floating Gold Circle Button (Bottom Corner) with a White Search Icon.

UI: Clicking it opens a Glassy Modal with a Foggy Backdrop.

Initial State: The modal is largely empty. It shows a "Sort By" section at the bottom and an "Add Rule" button at the top.

"Add Rule" Logic:

Clicking "Add Rule" opens a dropdown of ALL fields (see Translation Map).

Selecting a field adds a specific UI row for that rule.

Input Types & Logic:

Universal Null Check: EVERY field type (Text, Number, Date, Boolean) must have a dropdown option for "Is Empty" (Null) and "Is Full" (Not Null).

API: ?no_fieldname=true (Empty) or false (Full).

Text Fields: [Equals, Contains, Is Empty, Is Full].

API: field=val (Exact), field_contains=val (Partial).

Numbers: [Equals, Greater Than, Less Than, Is Empty, Is Full].

API: field=val, min_field=val, max_field=val.

Dates: [Equals, Is Empty, Is Full].

Calendar UI: Use a Gregorian (Christian) Calendar for input.

API Logic: Convert the selected Gregorian Date to Unix Timestamp (Seconds) and send as joined_after_unix / joined_before_unix.

Booleans: [Toggle True, Toggle False, Is Empty, Is Full].

Sorting: Dropdown to choose field + Asc/Desc (order_by=-field).

Apply: A Shiny Gold "Apply" Button.

3. User Details & Editing

Route: /users/[id]

Visual: Large Profile Image, full detailed list of all data.

Edit Trigger: A Floating Gold Button with an Edit Icon (Bottom Corner).

Edit Modal: Same logic as the Filter Modal (fields, dropdowns, calendars), but pre-filled with the user's current data.

Back Button Behavior: Clicking "Back" in the header MUST return the user to the /users list with their previous filters and pagination intact.

PART 5: API REFERENCE (REAL ENDPOINTS)

1. Get Users (List)

Endpoint: GET https://hoviat-admin-fast-api.onrender.com/api/admin/users-management/

Response:

code
JSON
download
content_copy
expand_less
{
  "data": [
    {
      "counter": 4749,
      "user_id": 100930312,
      "username": "alex_doe",
      "first_name": "Alex",
      "country": "Germany",
      "is_ban": false,
      "profile_path": "AQADAgADr6gxGy4MwBQACAMAAy4MwBQABK8vwaYURoamNgQ.jpg",
      "updated_at": "2025-11-27T09:17:09.310Z"
    }
  ],
  "meta": { "total": 45, "page": 1, "size": 20 }
}

Image Logic: If profile_path is present, the full URL is: https://pub-4036d35baed54ee7a9504072ea49740f.r2.dev/ + profile_path.

2. Get Single User

Endpoint: GET .../users-management/{id}

Response: (Standard JSON envelope as above).

3. Update User

Endpoint: PATCH .../users-management/update

Header: Content-Type: application/json

Body Example:

code
JSON
download
content_copy
expand_less
{
  "user_id": 895485628,
  "username": "NewName",
  "country": "Germany",
  "is_ban": true,
  "ban_time": 1763468864
}

4. Error Codes (Handle These)

401: "Could not validate credentials" (Redirect to login).

403: "Forbidden" (Show Toast).

404: "User not found".

422: "Invalid Input".

PART 6: DATA DICTIONARY (TRANSLATIONS)

You MUST use these exact Persian translations for the UI labels (in Tables, Cards, and Filter Dropdowns).

code
JSON
download
content_copy
expand_less
{
    "counter": "شمارنده",
    "user_id": "آیدی تلگرام",
    "accounting_code": "کد حسابداری",
    "username": "یوزر تلگرام",
    "first_name": "نام کوچک",
    "last_name": "نام خانوادگی",
    "nickname": "نام تلگرام",
    "phone_number": "شماره همراه",
    "whatsapp_number": "شماره واتساپ",
    "country": "کشور",
    "password": "رمز عبور",
    "mode": "حالت در ربات",
    "is_ban": "بن شده است",
    "is_registered": "رجیستر شده است",
    "chat_not_found": "چت یافت نمیشود",
    "score": "امتیاز",
    "ban_time": "تاریخ بن شدن",
    "join_date": "تاریخ عضویت",
    "profile_path": "مسیر پروفایل",
    "telegram_message_id": "آیدی پیام چنل اصلی",
    "group_message_id": "آیدی پیام کامنت اصلی",
    "public_message_id": "آیدی پیام چنل عمومی",
    "public_group_message_id": "آِیدی پیام کامنت عمومی",
    "updated_at": "تاریخ آخرین ویرایش",
    "channel_updated_at": "تاریخ آپدیت شدن چنل"
}
PART 7: EXECUTION PLAN

Initialize: Set up the Next.js app with dir="rtl" and the Vazirmatn font.

API Layer: Build lib/axios.ts with the specific Token and 403 Interceptor logic first.

Auth: Implement the Login page connected to the real API.

Layout: Build the Sidebar and Header with the "Static Glass" effect.

Users:

Build the Dynamic Filter Component (This is the most critical UI piece). Ensure the "Add Rule" -> "Universal Null Check" flow works.

the way filter modal works is that it doesnt show you any fields first , only sort at the bottom and at top a section that allows you to "add" field or rule . you click on it , it gives you a list of fields you can choose from and then based on what then thing is the field is created in a certain way . for example the texty ones have an option to be "include this" or "be exactly this" , the dates and date times have a few number boxes that each represent a section of the date time including year / month and so on , numbers must be numbers and booleans are toggles and so on .
and ofcourse you can add many rules but one rule for each field the api allows . meaning you can imagine we have every field and settings you can think of, but we hide them first and then you add them as much as you want .
Except for is_nulls , they will be integrated into that drop down , meaning that drop down that texts use to choose "included" or "equals" also has a "is full" and "is empty" , and the dates and stuff have the same thing however for them it doesnt have included it only has before and after and as is full and empty same thing with rest . so each thing must have things that the api allows for it 

in the edit form and filter form everything that the api allows must be included not just a few handfuls

dates must be chosen by calendar in christian calendar and should be shown in christian calendar meaning you have to convert somethings to each other . christian calendar i just mean regular universal .

filter must have choosing sorting option as the api allows it . it must be choosing field from drop down and choosing ascending vs descending .


Build the Card View and Row View.
card one :
the profile is shown in circle ,below it first name last name ,  below it telegram id below it country

the row view :

small profile "margin" field1 name below it>> field1 value "margin" field2 name below it >> field2 value

so you can see profile is first then other values like so , the order of fields should be based on relevance but should include almost everything except for very technical cody ones for example mode and profile path and so on . and the way they take space is that each pair will occupy space as much as it wants and have a constant margin with everything around it . so no "have some be left have some be right" or whatever else .







Wire up the TanStack Query hooks to sync with URL parameters.

 more things to be pay attention to :

  as I understand the glass effect is hard to achieve for moving objects so there would be one glass css thing for staying objects and one for moving objects since aperantly in some cases the browser turns that effect off when it is hard to calculate . the seperation helps to figure out how to have glass effect for anything wihtout problem .
the background should be a graphic white 

the project should be rtl and the rtlness should be taken into account for example this reverses the position of back button and so on .


 the back button in header shuold work in a way that when you are in "users list"page with a filter , then go to details of one user , then when you go back the filters dont get reset you go back to where you were and the same filters .

this is more details about how the filter api works :

GET /api/admin/users-management/

1. Pagination & Sorting
Parameter	Default	Description
page	1	Page number.
size	20	Items per page.
order_by	-counter	Sort field. Prefix with - for Descending. <br>(e.g., -score, join_date)
2. Filtering

All filters act as AND conditions.

A. Global Search

Param: search (Case-insensitive, partial).

Targets: username, first_name, last_name, nickname, accounting_code, phone_number, whatsapp_number, country.

B. Specific Field Filters
Filter Type	Usage	Supported Fields
Text (Exact)	field=value	username, first_name, last_name, nickname, country, phone_number, whatsapp_number, profile_path
Text (Partial)	field_contains=val	Same as above (auto-wildcard).
IDs/Codes	field=value	user_id, counter, accounting_code, mode, telegram_message_id, group_message_id, public_message_id, public_group_message_id
Boolean	field=true/false	is_ban, is_registered, chat_not_found
Numeric Range	min_{field}<br>max_{field}	score, ban_time
Date (Unix)	_after_unix<br>_before_unix	joined <br>(e.g., joined_after_unix=1747691518)
Date (ISO)	_after<br>_before	updated, channel_updated <br>(e.g., updated_after=2024-01-01T00:00:00Z)
Null Checks	no_{field}=true	user_id, accounting_code, username, first_name, last_name, nickname, phone_number, whatsapp_number, country, password, mode, join_date, profile_path, telegram_msg_id, group_msg_id, public_msg_id, public_group_msg_id, channel_update
3. Response Structure

Success (200 OK)

code
JSON
download
content_copy
expand_less
{
  "data": [
    {
      "counter": 4749,
      "user_id": 100930312,
      "username": "alex_doe",
      "score": 50,
      "join_date": 1747691518,
      "is_ban": false,
      ...
    }
  ],
  "meta": {
    "total": 45,
    "page": 1,
    "size": 20,
    "pages": 3
  },
  "error": {}
}

Error (401, 403, 422)

code
JSON
download
content_copy
expand_less
{
  "data": {},
  "meta": {},
  "error": { "code": "INVALID_INPUT", "message": "..." }
}

you can view a list of users in different ways ,
there is a floating search button and bottom corner that when you click on it shows you a modal where you can set filters and apply to get the filtered users .
the floating search thing will be a circle that will look like it is shiny gold paper and has a white search icon . the modal that opens will be glassy and makes the backdrop foggy and when you click outside it will go . it will have a gold apply button .