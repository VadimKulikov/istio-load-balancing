# Build stage
FROM golang:1.21-alpine AS builder

WORKDIR /app

COPY main.go .
RUN go mod init go-server && go mod tidy
RUN go build -o server main.go

# Final stage
FROM alpine:latest

WORKDIR /app

COPY --from=builder /app/server .

EXPOSE 8080

ENTRYPOINT ["./server"]
