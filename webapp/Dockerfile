# Web app container (Cloud Run). No npm packages are needed.
FROM node:22-alpine
WORKDIR /app
COPY package.json server.js ./
COPY public ./public
# the robot package is served at /oasis_voice_robot.zip so the robot can update itself
ENV NODE_ENV=production
EXPOSE 8080
CMD ["node", "server.js"]
