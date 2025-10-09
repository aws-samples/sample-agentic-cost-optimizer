# Implementation Plan

- [x] 1. Add DynamoDB journaling instructions to system prompt only

  - Add DynamoDB table name environment variable reference to ENVIRONMENT section (assume JOURNAL_TABLE_NAME will be provided)
  - Define session and task record structures with required attributes in prompt
  - Add instructions for using existing DynamoDB table via use_aws tool
  - Add instructions for table creation if it doesn't exist using use_aws tool
  - Ensure all journaling logic is contained within the system prompt
  - _Requirements: 1.4, 5.1, 5.2, 5.3_

- [x] 2. Implement session management journaling in system prompt

  - Add instructions to create session record at workflow start with "STARTED" status
  - Add instructions to update session record to "COMPLETED" status at workflow end
  - Include session timing and duration calculations
  - Add error handling for session record failures
  - _Requirements: 1.1, 1.2, 1.3, 6.1, 6.2_

- [x] 3. Add phase tracking for Discovery workflow in system prompt

  - Add instructions to create task record when Discovery phase starts
  - Add instructions to update task status to "COMPLETED" when Discovery finishes
  - Include resource count tracking for discovered services
  - Add error handling to continue workflow if journaling fails
  - _Requirements: 2.1, 2.2, 3.1, 3.4, 4.1, 4.2, 4.4_

- [x] 4. Add phase tracking for Usage and Metrics Collection workflow in system prompt

  - Add instructions to create task record when metrics collection starts
  - Add instructions to update task status based on metrics gathering success
  - Include timing and resource count tracking for this phase
  - Ensure journaling failures don't interrupt metrics collection
  - _Requirements: 2.1, 2.2, 3.1, 3.4, 4.1, 4.2, 4.4, 7.1, 7.2, 7.3_

- [x] 5. Add phase tracking for Analysis and Decision Rules workflow in system prompt

  - Add instructions to create task record when analysis phase starts
  - Add instructions to update task status when analysis completes
  - Include count of recommendations generated in the task record
  - Maintain existing analysis logic while adding journaling
  - _Requirements: 2.1, 2.2, 3.1, 3.4, 4.1, 4.2, 4.4_

- [-] 6. Add phase tracking for remaining workflow phases in system prompt
- [x] 6.1 Add task tracking for Recommendation Format phase (phase 4)
  - Add task tracking start instructions before recommendation formatting begins
  - Add task tracking completion instructions after recommendation formatting ends
  - Include error handling for failed recommendation formatting
  - _Requirements: 2.1, 2.2, 3.1, 3.4, 4.1, 4.2, 4.4_
- [x] 6.2 Add task tracking for Cost Estimation Method phase (phase 5)
  - Add task tracking start instructions before cost estimation begins
  - Add task tracking completion instructions after cost estimation ends
  - Include error handling for failed cost estimation
  - _Requirements: 2.1, 2.2, 3.1, 3.4, 4.1, 4.2, 4.4_
- [x] 6.3 Add task tracking for Output Contract phase (phase 6)
  - Add task tracking start instructions before output contract generation begins
  - Add task tracking completion instructions after output contract generation ends
  - Include error handling for failed output contract generation
  - _Requirements: 2.1, 2.2, 3.1, 3.4, 4.1, 4.2, 4.4_
- [-] 6.4 Add task tracking for S3 Write Requirements phase (phase 7)
  - Add task tracking start instructions before S3 write operations begin
  - Add task tracking completion instructions after S3 write operations end
  - Include error handling for failed S3 write operations
  - _Requirements: 2.1, 2.2, 3.1, 3.4, 4.1, 4.2, 4.4_
- [ ] 6.5 Add task tracking for Error Handling and Fallbacks phase (phase 8)

  - Add task tracking start instructions before error handling phase begins
  - Add task tracking completion instructions after error handling phase ends
  - Include error handling for the error handling phase itself
  - _Requirements: 2.1, 2.2, 3.1, 3.4, 4.1, 4.2, 4.4_

- [x] 7. Add retry logic and error handling for DynamoDB operations in system prompt

  - Add instructions for exponential backoff retry (up to 3 attempts)
  - Add instructions to log DynamoDB errors but continue workflow
  - Add instructions to handle DynamoDB unavailability gracefully
  - Ensure core cost optimization workflow is never interrupted by journaling failures
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ] 8. Add performance metrics tracking to journal records in system prompt

  - Add instructions to record start and end timestamps for each phase
  - Add instructions to calculate and store duration for completed phases
  - Add instructions to track resource counts processed in each phase
  - Add instructions to record total session execution time
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [ ] 9. Finalize system prompt with integrated DynamoDB journaling workflow

  - Integrate all journaling instructions into the existing system prompt structure
  - Add journaling instructions to each phase of the DETERMINISTIC WORKFLOW section
  - Add DynamoDB table management to ENVIRONMENT section
  - Update ERROR HANDLING section to include journaling failure handling
  - Ensure journaling instructions don't interfere with existing S3 reporting
  - _Requirements: 1.1, 2.1, 4.1, 5.1, 6.1_

- [ ] 10. Deploy and validate journaling functionality
  - Deploy updated system prompt to existing Agent Core runtime
  - Trigger cost optimization analysis and verify DynamoDB table creation
  - Verify all workflow phases are tracked with correct statuses and timestamps
  - Confirm that journaling failures don't break core cost optimization workflow
  - Validate that session records provide complete execution summary
  - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1_
