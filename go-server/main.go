package main

import (
	"flag"
	"fmt"
	"log"
	"net/http"
	"time"
)

func main() {
	var text string
	var port string
	var delay int

	flag.StringVar(&text, "text", "Hello, World!", "Text to return in responses")
	flag.StringVar(&port, "port", "8080", "Port to listen on")
	flag.IntVar(&delay, "delay", 0, "Delay in milliseconds before responding")
	flag.Parse()

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if delay > 0 {
			time.Sleep(time.Duration(delay) * time.Millisecond)
		}
		w.Header().Set("Content-Type", "text/plain")
		fmt.Fprint(w, text)
	})

	addr := ":" + port
	log.Printf("Server starting on %s", addr)
	log.Printf("Response text: %s", text)
	if err := http.ListenAndServe(addr, nil); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}
