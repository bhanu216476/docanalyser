package com.docanalyser.controller;

import com.docanalyser.dto.request.MessageRequest;
import com.docanalyser.dto.request.SessionRequest;
import com.docanalyser.entity.ChatMessage;
import com.docanalyser.entity.ChatRole;
import com.docanalyser.entity.ChatSession;
import com.docanalyser.security.services.UserDetailsImpl;
import com.docanalyser.service.ChatService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.authority.SimpleGrantedAuthority;

import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ChatControllerTest {

    @Mock
    private ChatService chatService;

    @InjectMocks
    private ChatController chatController;

    private UserDetailsImpl userDetails;
    private UUID userId;
    private UUID sessionId;
    private ChatSession session;

    @BeforeEach
    void setUp() {
        userId = UUID.randomUUID();
        sessionId = UUID.randomUUID();
        userDetails = new UserDetailsImpl(
                userId, "Test User", "test@example.com", "hash",
                List.of(new SimpleGrantedAuthority("ROLE_USER")), true
        );
        session = new ChatSession(userId, "My Research Session");
    }

    @Test
    @DisplayName("POST /api/chat/sessions creates and returns session")
    void createSession_validRequest_returnsOk() {
        SessionRequest request = new SessionRequest();
        request.setTitle("My Research Session");

        when(chatService.createSession(eq("My Research Session"), eq(userDetails))).thenReturn(session);

        ResponseEntity<ChatSession> response = chatController.createSession(request, userDetails);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().getTitle()).isEqualTo("My Research Session");
        verify(chatService).createSession("My Research Session", userDetails);
    }

    @Test
    @DisplayName("GET /api/chat/sessions returns list of user sessions")
    void getSessions_returnsList() {
        when(chatService.getUserSessions(userDetails)).thenReturn(List.of(session));

        ResponseEntity<List<ChatSession>> response = chatController.getSessions(userDetails);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).hasSize(1);
        assertThat(response.getBody().get(0).getTitle()).isEqualTo("My Research Session");
        verify(chatService).getUserSessions(userDetails);
    }

    @Test
    @DisplayName("GET /api/chat/sessions/{id} returns session by ID")
    void getSession_owner_returnsSession() {
        when(chatService.getSession(sessionId, userDetails)).thenReturn(session);

        ResponseEntity<ChatSession> response = chatController.getSession(sessionId, userDetails);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().getUserId()).isEqualTo(userId);
        verify(chatService).getSession(sessionId, userDetails);
    }

    @Test
    @DisplayName("GET /api/chat/sessions/{id} throws AccessDeniedException for unauthorized user")
    void getSession_unauthorized_throwsAccessDenied() {
        when(chatService.getSession(sessionId, userDetails))
                .thenThrow(new AccessDeniedException("Access is denied"));

        assertThatThrownBy(() -> chatController.getSession(sessionId, userDetails))
                .isInstanceOf(AccessDeniedException.class)
                .hasMessage("Access is denied");
    }

    @Test
    @DisplayName("DELETE /api/chat/sessions/{id} deletes session")
    void deleteSession_success_returnsOk() {
        ResponseEntity<?> response = chatController.deleteSession(sessionId, userDetails);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        verify(chatService).deleteSession(sessionId, userDetails);
    }

    @Test
    @DisplayName("POST /api/chat/sessions/{id}/messages sends message and returns reply")
    void sendMessage_validMessage_returnsAssistantMessage() {
        MessageRequest request = new MessageRequest();
        request.setContent("What is the leave policy?");

        ChatMessage reply = new ChatMessage(sessionId, ChatRole.ASSISTANT, "You get 12 days casual leave [1].");
        when(chatService.sendMessage(eq(sessionId), eq("What is the leave policy?"), eq(userDetails)))
                .thenReturn(reply);

        ResponseEntity<ChatMessage> response = chatController.sendMessage(sessionId, request, userDetails);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().getRole()).isEqualTo(ChatRole.ASSISTANT);
        assertThat(response.getBody().getContent()).contains("12 days casual leave");
        verify(chatService).sendMessage(sessionId, "What is the leave policy?", userDetails);
    }

    @Test
    @DisplayName("GET /api/chat/sessions/{id}/messages returns message history")
    void getMessages_returnsMessageList() {
        ChatMessage msgUser = new ChatMessage(sessionId, ChatRole.USER, "Hello");
        ChatMessage msgAssistant = new ChatMessage(sessionId, ChatRole.ASSISTANT, "Hello, how can I help?");

        when(chatService.getMessages(sessionId, userDetails)).thenReturn(List.of(msgUser, msgAssistant));

        ResponseEntity<List<ChatMessage>> response = chatController.getMessages(sessionId, userDetails);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).hasSize(2);
        assertThat(response.getBody().get(0).getContent()).isEqualTo("Hello");
        assertThat(response.getBody().get(1).getContent()).isEqualTo("Hello, how can I help?");
        verify(chatService).getMessages(sessionId, userDetails);
    }
}
