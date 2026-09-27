package com.docanalyser.controller;

import com.docanalyser.dto.request.MessageRequest;
import com.docanalyser.dto.request.SessionRequest;
import com.docanalyser.entity.ChatMessage;
import com.docanalyser.entity.ChatSession;
import com.docanalyser.security.services.UserDetailsImpl;
import com.docanalyser.service.ChatService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/chat")
public class ChatController {

    private final ChatService chatService;

    public ChatController(ChatService chatService) {
        this.chatService = chatService;
    }

    @PostMapping("/sessions")
    public ResponseEntity<ChatSession> createSession(@Valid @RequestBody SessionRequest request,
                                                     @AuthenticationPrincipal UserDetailsImpl userDetails) {
        return ResponseEntity.ok(chatService.createSession(request.getTitle(), userDetails));
    }

    @GetMapping("/sessions")
    public ResponseEntity<List<ChatSession>> getSessions(@AuthenticationPrincipal UserDetailsImpl userDetails) {
        return ResponseEntity.ok(chatService.getUserSessions(userDetails));
    }

    @GetMapping("/sessions/{id}")
    public ResponseEntity<ChatSession> getSession(@PathVariable UUID id, @AuthenticationPrincipal UserDetailsImpl userDetails) {
        return ResponseEntity.ok(chatService.getSession(id, userDetails));
    }

    @DeleteMapping("/sessions/{id}")
    public ResponseEntity<?> deleteSession(@PathVariable UUID id, @AuthenticationPrincipal UserDetailsImpl userDetails) {
        chatService.deleteSession(id, userDetails);
        return ResponseEntity.ok().build();
    }

    @PostMapping("/sessions/{id}/messages")
    public ResponseEntity<ChatMessage> sendMessage(@PathVariable UUID id,
                                                   @Valid @RequestBody MessageRequest request,
                                                   @AuthenticationPrincipal UserDetailsImpl userDetails) {
        return ResponseEntity.ok(chatService.sendMessage(id, request.getContent(), userDetails));
    }
    
    @GetMapping("/sessions/{id}/messages")
    public ResponseEntity<List<ChatMessage>> getMessages(@PathVariable UUID id, @AuthenticationPrincipal UserDetailsImpl userDetails) {
        return ResponseEntity.ok(chatService.getMessages(id, userDetails));
    }
}
