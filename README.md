This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started Frontedn
cd .\Searching-public-footprint\
cd .\Frontend\

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.
______________________________________________________________________________________________
## Getting Started Backend
cd Searching-public-footprint/Backend/src

# First time only — install dependencies
pip install -r requirements.txt

## stay at backend
cd ..

# Start the API (allow the same network device to access the localhost)
uvicorn src.Logic:app --reload --host 0.0.0.0 --port 8000

## Running the backend
uvicorn src.Logic:app --reload --port 8000
________________________________________________________________________________________________

## Run Ollama
ollama pull qwen2.5:14b

________________________________________________________________________________________________

## Testing Program

# One name for all
python test.py --name "username" --req "Python"

# Different per platform
python test.py --github "u1" --linkedin "u2" --scholar "u3"

# Mix
python test.py --name "default" --github "custom"

# Mock only
python test.py --mock-only --github "username"

# Full test
python test.py --github "u1" --linkedin "u2" --req "Python" --req "ML"
```
________________________________________________________________________________________________


## Testing fro andidateSeacher.py

cd Testing\src

python test_url_searching.py --verbose --live
________________________________________________________________________________________________

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
