package com.docanalyser.service;

import com.docanalyser.entity.ChatMessage;
import com.docanalyser.entity.ChatRole;
import com.docanalyser.entity.ChatSession;
import com.docanalyser.repository.ChatMessageRepository;
import com.docanalyser.repository.ChatSessionRepository;
import com.docanalyser.security.services.UserDetailsImpl;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ChatServiceTest {

    @Mock
    private ChatSessionRepository sessionRepository;
    @Mock
    private ChatMessageRepository messageRepository;
    @Mock
    private RagServiceClient ragServiceClient;

    @InjectMocks
    private ChatService chatService;

    private UUID userId;
    private UUID otherUserId;
    private UUID sessionId;
    private UserDetailsImpl userDetails;
    private UserDetailsImpl otherUserDetails;
    private ChatSession session;

    @BeforeEach
    void setUp() {
        userId = UUID.randomUUID();
        otherUserId = UUID.randomUUID();
        sessionId = UUID.randomUUID();

        List<GrantedAuthority> userAuthorities = List.of(new SimpleGrantedAuthority("ROLE_USER"));
        List<GrantedAuthority> otherAuthorities = List.of(new SimpleGrantedAuthority("ROLE_USER"));
        userDetails = new UserDetailsImpl(userId, "User", "user@example.com", "hash",
                userAuthorities, true);
        otherUserDetails = new UserDetailsImpl(otherUserId, "Other", "other@example.com", "hash",
                otherAuthorities, true);

        session = new ChatSession(userId, "Test Session");
    }

    @Test
    void createSession_validUser_returnsNewSession() {
        when(sessionRepository.save(any())).thenReturn(session);

        ChatSession result = chatService.createSession("Test Session", userDetails);

        assertThat(result.getTitle()).isEqualTo("Test Session");
    }

    @Test
    void getUserSessions_returnsOnlyUserSessions() {
        when(sessionRepository.findByUserIdOrderByCreatedAtDesc(userId)).thenReturn(List.of(session));

        List<ChatSession> sessions = chatService.getUserSessions(userDetails);

        assertThat(sessions).hasSize(1);
    }

    @Test
    void getSession_owner_returnsSession() {
        when(sessionRepository.findById(sessionId)).thenReturn(Optional.of(session));

        ChatSession result = chatService.getSession(sessionId, userDetails);

        assertThat(result.getUserId()).isEqualTo(userId);
    }

    @Test
    void getSession_otherUser_throwsAccessDenied() {
        when(sessionRepository.findById(sessionId)).thenReturn(Optional.of(session));

        assertThatThrownBy(() -> chatService.getSession(sessionId, otherUserDetails))
                .isInstanceOf(AccessDeniedException.class);
    }

    @Test
    void getSession_notFound_throwsException() {
        when(sessionRepository.findById(sessionId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> chatService.getSession(sessionId, userDetails))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("not found");
    }

    @Test
    void sendMessage_validSession_returnsAssistantMessage() {
        when(sessionRepository.findById(sessionId)).thenReturn(Optional.of(session));
        when(messageRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));
        when(ragServiceClient.queryRagService("Hello?"))
                .thenReturn(Map.of("answer", "Hello from RAG!"));

        ChatMessage result = chatService.sendMessage(sessionId, "Hello?", userDetails);

        assertThat(result.getRole()).isEqualTo(ChatRole.ASSISTANT);
        assertThat(result.getContent()).isEqualTo("Hello from RAG!");
    }

    @Test
    void sendMessage_ragServiceUnavailable_returnsErrorMessage() {
        when(sessionRepository.findById(sessionId)).thenReturn(Optional.of(session));
        when(messageRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));
        when(ragServiceClient.queryRagService("Hello?"))
                .thenThrow(new RuntimeException("Service unavailable"));

        ChatMessage result = chatService.sendMessage(sessionId, "Hello?", userDetails);

        assertThat(result.getRole()).isEqualTo(ChatRole.ASSISTANT);
        assertThat(result.getContent()).contains("unable to process");
    }
}
