# The Firebase Auth emulator, for the load-test stack only.
FROM node:24-slim
RUN npm install --global --no-fund --no-audit firebase-tools@15.30.2
WORKDIR /emulator
COPY firebase.json .
EXPOSE 9099
CMD ["firebase", "emulators:start", "--only", "auth", "--project", "demo-thapargenie"]
